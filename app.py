"""FastAPI app exposing /health and /analyze-ticket.

This module owns:
    * endpoint signatures and Pydantic request validation
    * HTTP status code mapping (200, 400, 422, 500)
    * orchestration of investigator -> classifier -> safety
    * global exception handlers that never leak stack traces

The three worker modules are intentionally pure-Python so they can be
unit-tested without spinning up the app.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from schemas import AnalyzeRequest, AnalyzeResponse, HealthResponse
from investigator import investigate
from classifier import classify
from safety import build_response_fields
from utils.text import normalize


logger = logging.getLogger("ticket_classifier")
logging.basicConfig(level=logging.INFO)


app = FastAPI(
    title="Financial Ticket Classifier",
    version="1.0.0",
    description="Internal copilot for fintech support agents.",
)


# --- Helpers ----------------------------------------------------------------

def _txn_amount_counterparty(history: list[dict], txn_id: Optional[str]) -> tuple[Optional[float], Optional[str]]:
    """Pull amount and counterparty out of the matched history entry, if any."""
    if not txn_id:
        return None, None
    for entry in history:
        if entry.get("transaction_id") == txn_id:
            return entry.get("amount"), entry.get("counterparty")
    return None, None


def _build_agent_summary(
    complaint: str,
    case_type: str,
    verdict: str,
    txn_id: Optional[str],
) -> str:
    """One-to-two-sentence summary for the support agent (internal)."""
    short = complaint.strip()
    if len(short) > 240:
        short = short[:237].rstrip() + "..."
    txn_phrase = f" Related transaction: {txn_id}." if txn_id else ""
    verdict_phrase = {
        "consistent": "The provided transaction history supports the complaint.",
        "inconsistent": "The provided transaction history appears to contradict the complaint.",
        "insufficient_data": "The provided transaction history is not enough to verify the complaint.",
    }.get(verdict, "")
    return f"Customer reports: {short}{txn_phrase} {verdict_phrase}".strip()


# --- Endpoints --------------------------------------------------------------

@app.get("/health", response_model=HealthResponse)
def health() -> dict:
    """Readiness probe. Always returns 200 with `status: ok`."""
    return {"status": "ok"}


@app.post("/analyze-ticket", response_model=AnalyzeResponse)
def analyze_ticket(payload: AnalyzeRequest) -> dict:
    """Analyze one ticket and return a structured JSON response."""
    history = [t.model_dump() for t in payload.transaction_history]

    inv = investigate(payload.complaint, history)
    txn_id: Optional[str] = inv.get("relevant_transaction_id")
    verdict: str = inv.get("evidence_verdict", "insufficient_data")

    cls = classify(payload.complaint, verdict, txn_id)
    case_type: str = cls["case_type"]

    amount, counterparty = _txn_amount_counterparty(history, txn_id)
    agent_summary = _build_agent_summary(payload.complaint, case_type, verdict, txn_id)

    safety_out = build_response_fields(
        case_type=case_type,
        verdict=verdict,
        txn_id=txn_id,
        txn_amount=amount,
        txn_counterparty=counterparty,
        ticket_id=payload.ticket_id,
        base_human_review=cls["human_review_required"],
        agent_summary=agent_summary,
    )

    # Merge reason codes from investigator + classifier.
    merged_reasons = list(dict.fromkeys(
        list(inv.get("reason_codes", [])) + list(cls.get("reason_codes", []))
    ))

    response = {
        "ticket_id": payload.ticket_id,
        "relevant_transaction_id": txn_id,
        "evidence_verdict": verdict,
        "case_type": case_type,
        "severity": cls["severity"],
        "department": cls["department"],
        "agent_summary": safety_out["agent_summary"],
        "recommended_next_action": safety_out["recommended_next_action"],
        "customer_reply": safety_out["customer_reply"],
        "human_review_required": safety_out["human_review_required"],
        "confidence": cls["confidence"],
        "reason_codes": merged_reasons,
    }

    # Pydantic round-trip ensures the response conforms to the schema
    # exactly. Any drift raises ValidationError and is converted to 500
    # by the global handler.
    return AnalyzeResponse(**response).model_dump()


# --- Exception handlers -----------------------------------------------------

@app.exception_handler(RequestValidationError)
async def _on_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Map FastAPI's RequestValidationError to 400 with a safe message."""
    safe_msg = "Malformed or invalid input."
    logger.info("validation_error on %s: %s", request.url.path, exc.errors())
    return JSONResponse(
        status_code=400,
        content={"error": safe_msg, "detail": "request body failed validation"},
    )


@app.exception_handler(ValidationError)
async def _on_pydantic_error(request: Request, exc: ValidationError) -> JSONResponse:
    logger.info("pydantic_error on %s: %s", request.url.path, exc.errors())
    return JSONResponse(
        status_code=400,
        content={"error": "Invalid input.", "detail": "schema validation failed"},
    )


@app.exception_handler(Exception)
async def _on_unhandled(request: Request, exc: Exception) -> JSONResponse:
    """Last-resort handler. Never expose stack traces, tokens, or secrets."""
    logger.exception("unhandled error on %s", request.url.path)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error."},
    )
