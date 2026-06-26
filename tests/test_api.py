"""End-to-end tests for the FastAPI surface (sections 5, 6, 7 of spec).

These tests use FastAPI's TestClient against the real `app.app` instance.
They cover:
    * /health contract
    * /analyze-ticket happy-path response shape (all 11 fields)
    * status code mapping (200, 400, 500)
    * exception handlers never leak stack traces
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app import app

client = TestClient(app)


# --------------------------------------------------------------------------
# /health
# --------------------------------------------------------------------------


def test_health_returns_ok():
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"status": "ok"}


def test_health_does_not_require_body():
    resp = client.get("/health")
    # No payload should be required; nothing should be in the query string.
    assert resp.status_code == 200


# --------------------------------------------------------------------------
# /analyze-ticket contract
# --------------------------------------------------------------------------


def _base_history():
    return [
        {
            "transaction_id": "TX-1",
            "timestamp": "2026-06-26T10:00:00Z",
            "type": "transfer",
            "amount": 3000.0,
            "counterparty": "+8801712345678",
            "status": "completed",
        }
    ]


def test_analyze_ticket_returns_all_required_fields():
    resp = client.post(
        "/analyze-ticket",
        json={
            "ticket_id": "T-CONTRACT",
            "complaint": "I sent 3000 to a wrong number",
            "transaction_history": _base_history(),
        },
    )
    assert resp.status_code == 200
    body = resp.json()

    required = {
        "ticket_id",
        "relevant_transaction_id",
        "evidence_verdict",
        "case_type",
        "severity",
        "department",
        "agent_summary",
        "recommended_next_action",
        "customer_reply",
        "human_review_required",
        "confidence",
        "reason_codes",
    }
    assert required.issubset(body.keys()), f"missing fields: {required - set(body.keys())}"


def test_analyze_ticket_rejects_empty_complaint():
    resp = client.post(
        "/analyze-ticket",
        json={
            "ticket_id": "T-EMPTY",
            "complaint": "",
            "transaction_history": [],
        },
    )
    # min_length=1 in schemas -> Pydantic validation error -> 400
    assert resp.status_code == 400
    assert "error" in resp.json()


def test_analyze_ticket_rejects_missing_ticket_id():
    resp = client.post(
        "/analyze-ticket",
        json={
            "complaint": "I sent money to a wrong number",
            "transaction_history": [],
        },
    )
    assert resp.status_code == 400


def test_analyze_ticket_rejects_malformed_json():
    resp = client.post(
        "/analyze-ticket",
        json={"ticket_id": "T-X", "complaint": "x", "transaction_history": "not a list"},
    )
    assert resp.status_code == 400


def test_analyze_ticket_handles_missing_history():
    """Empty / omitted transaction history should not 500 — verdict is
    insufficient_data and human_review_required is forced True."""
    resp = client.post(
        "/analyze-ticket",
        json={"ticket_id": "T-NO-HIST", "complaint": "App crashed"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["evidence_verdict"] == "insufficient_data"
    assert body["relevant_transaction_id"] is None
    assert body["human_review_required"] is True


def test_analyze_ticket_confidence_within_bounds():
    resp = client.post(
        "/analyze-ticket",
        json={
            "ticket_id": "T-CFG",
            "complaint": "Wrong number, I sent 3000 to the wrong person",
            "transaction_history": _base_history(),
        },
    )
    assert resp.status_code == 200
    assert 0.0 <= resp.json()["confidence"] <= 1.0


def test_analyze_ticket_reason_codes_is_list():
    resp = client.post(
        "/analyze-ticket",
        json={
            "ticket_id": "T-REASONS",
            "complaint": "Payment failed but my balance was deducted 3000",
            "transaction_history": _base_history(),
        },
    )
    assert resp.status_code == 200
    assert isinstance(resp.json()["reason_codes"], list)


def test_analyze_ticket_unknown_endpoint_returns_404():
    resp = client.get("/no-such-route")
    assert resp.status_code == 404


# --------------------------------------------------------------------------
# Exception handler does not leak internals
# --------------------------------------------------------------------------


def test_unhandled_exception_does_not_leak_stack(monkeypatch):
    """Force investigator.investigate to raise, then verify the 500
    response contains only a safe message — no Python traceback text."""
    import sys

    import app as app_module  # the Python module (not the FastAPI instance)
    from fastapi.testclient import TestClient

    def _boom(_complaint, _history):
        raise RuntimeError("SECRET_TOKEN_LEAK_DO_NOT_SHOW abc123secret")

    monkeypatch.setattr(app_module, "investigate", _boom)

    # raise_server_exceptions=False so the exception handler runs and the
    # test can inspect the safe 500 body instead of getting a re-raise.
    c = TestClient(app_module.app, raise_server_exceptions=False)
    resp = c.post(
        "/analyze-ticket",
        json={
            "ticket_id": "T-LEAK",
            "complaint": "Anything",
            "transaction_history": [],
        },
    )
    assert resp.status_code == 500
    body = resp.json()
    assert body == {"error": "Internal server error."}
    assert "SECRET_TOKEN_LEAK" not in str(body)
    assert "Traceback" not in str(body)
