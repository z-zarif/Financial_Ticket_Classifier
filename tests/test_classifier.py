"""Unit tests for classifier.classify.

Covers every case_type, the phishing floor, verdict-based severity
adjustments, and the human_review_required logic.
"""

from __future__ import annotations

from classifier import classify


def _c(text, verdict="insufficient_data", txn_id=None):
    return classify(text, verdict, txn_id)


def test_phishing_is_always_critical_and_human_review():
    out = _c("Someone called me asking for my OTP, is that legit?", "insufficient_data")
    assert out["case_type"] == "phishing_or_social_engineering"
    assert out["severity"] == "critical"
    assert out["department"] == "fraud_risk"
    assert out["human_review_required"] is True
    assert "phishing_floor" in out["reason_codes"]


def test_wrong_transfer_classified_and_high_severity():
    out = _c("I sent 3000 to a wrong number", "consistent", "TX-1")
    assert out["case_type"] == "wrong_transfer"
    assert out["severity"] == "high"
    assert out["human_review_required"] is True


def test_payment_failed_classified_high_severity():
    out = _c("Payment failed but balance deducted 3000", "consistent", "TX-1")
    assert out["case_type"] == "payment_failed"
    assert out["severity"] == "high"
    assert out["department"] == "payments_ops"


def test_refund_request_classified_low_severity():
    out = _c("Please refund my last transaction", "consistent", "TX-1")
    assert out["case_type"] == "refund_request"
    assert out["severity"] == "low"


def test_duplicate_payment_classified_high_severity():
    out = _c("I was charged twice for the same payment of 500", "consistent", "TX-1")
    assert out["case_type"] == "duplicate_payment"
    assert out["severity"] == "high"
    assert out["department"] == "payments_ops"


def test_merchant_settlement_classified():
    out = _c("Merchant settlement not received for last week", "consistent", "TX-1")
    assert out["case_type"] == "merchant_settlement_delay"
    assert out["department"] == "merchant_operations"


def test_agent_cash_in_issue_classified():
    out = _c("Agent did not deposit my cash in", "consistent", "TX-1")
    assert out["case_type"] == "agent_cash_in_issue"
    assert out["department"] == "agent_operations"


def test_other_fallback_when_no_keywords_match():
    out = _c("My app crashed when I opened it today", "insufficient_data")
    assert out["case_type"] == "other"
    # With insufficient_data verdict, severity floors to medium (per spec).
    assert out["severity"] == "medium"


def test_inconsistent_verdict_escalates_severity_and_review():
    """A contested claim (verdict=inconsistent) must trigger human review
    and bump severity for contested case types."""
    out = _c("Payment failed but balance deducted", "inconsistent", "TX-1")
    assert out["human_review_required"] is True
    assert "evidence_inconsistent" in out["reason_codes"]
    # Severity should be at least "high" for payment_failed + inconsistent.
    assert out["severity"] in ("high", "critical")


def test_consistent_verdict_with_txn_id_increases_confidence():
    low = _c("Refund my money please", "insufficient_data", None)
    high = _c("Refund my money please", "consistent", "TX-1")
    assert high["confidence"] >= low["confidence"]


def test_insufficient_data_lowers_confidence_below_one():
    out = _c("App crashed", "insufficient_data", None)
    assert out["confidence"] < 1.0


def test_confidence_within_unit_interval():
    for verdict in ("consistent", "inconsistent", "insufficient_data"):
        out = _c("Refund please", verdict, "TX-1")
        assert 0.0 <= out["confidence"] <= 1.0
