"""Pydantic schemas for request and response bodies.

These models are the single source of truth for the API contract described
in sections 5 and 6 of the problem statement. Enum values must match the
problem statement exactly — the judge harness scores variant spelling as
a schema violation.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


# --- Request side -----------------------------------------------------------

Language = Literal["en", "bn", "mixed"]
Channel = Literal[
    "in_app_chat", "call_center", "email", "merchant_portal", "field_agent"
]
UserType = Literal["customer", "merchant", "agent", "unknown"]
TxnType = Literal[
    "transfer", "payment", "cash_in", "cash_out", "settlement", "refund"
]
TxnStatus = Literal["completed", "failed", "pending", "reversed"]


class TransactionEntry(BaseModel):
    model_config = ConfigDict(extra="allow")

    transaction_id: str
    timestamp: str = Field(..., description="ISO 8601 timestamp")
    type: TxnType
    amount: float
    counterparty: str
    status: TxnStatus


class AnalyzeRequest(BaseModel):
    model_config = ConfigDict(extra="allow")

    ticket_id: str
    complaint: str = Field(..., min_length=1)
    language: Optional[Language] = None
    channel: Optional[Channel] = None
    user_type: Optional[UserType] = None
    campaign_context: Optional[str] = None
    transaction_history: list[TransactionEntry] = Field(default_factory=list)
    metadata: Optional[dict] = None


# --- Response side ----------------------------------------------------------

EvidenceVerdict = Literal["consistent", "inconsistent", "insufficient_data"]

CaseType = Literal[
    "wrong_transfer",
    "payment_failed",
    "refund_request",
    "duplicate_payment",
    "merchant_settlement_delay",
    "agent_cash_in_issue",
    "phishing_or_social_engineering",
    "other",
]

Severity = Literal["low", "medium", "high", "critical"]

Department = Literal[
    "customer_support",
    "dispute_resolution",
    "payments_ops",
    "merchant_operations",
    "agent_operations",
    "fraud_risk",
]


class AnalyzeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ticket_id: str
    relevant_transaction_id: Optional[str] = None
    evidence_verdict: EvidenceVerdict
    case_type: CaseType
    severity: Severity
    department: Department
    agent_summary: str
    recommended_next_action: str
    customer_reply: str
    human_review_required: bool
    confidence: float = Field(..., ge=0.0, le=1.0)
    reason_codes: list[str] = Field(default_factory=list)


# --- Health ---------------------------------------------------------------

class HealthResponse(BaseModel):
    status: Literal["ok"]
