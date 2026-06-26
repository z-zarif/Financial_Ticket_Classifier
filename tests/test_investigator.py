"""Unit tests for investigator.investigate (transaction matching + verdict).

Covers the three verdict branches and the core scoring signals
(amount, counterparty, time proximity).
"""

from __future__ import annotations

from investigator import investigate


def _entry(**kwargs):
    base = {
        "transaction_id": "TX-1",
        "timestamp": "2026-06-26T10:00:00Z",
        "type": "transfer",
        "amount": 3000.0,
        "counterparty": "+8801712345678",
        "status": "completed",
    }
    base.update(kwargs)
    return base


def test_empty_history_returns_insufficient():
    out = investigate("I sent 3000 to wrong number", [])
    assert out["relevant_transaction_id"] is None
    assert out["evidence_verdict"] == "insufficient_data"
    assert "empty_history" in out["reason_codes"]


def test_exact_amount_and_phone_match_returns_consistent():
    history = [_entry(transaction_id="TX-MATCH", amount=3000.0,
                      counterparty="+8801712345678")]
    out = investigate("I sent 3000 to +8801712345678 wrong number", history)
    assert out["relevant_transaction_id"] == "TX-MATCH"
    assert out["evidence_verdict"] == "consistent"
    assert "amount_match_exact" in out["reason_codes"]
    assert "counterparty_match" in out["reason_codes"]


def test_amount_mismatch_returns_inconsistent():
    history = [_entry(transaction_id="TX-MISMATCH", amount=500.0,
                      counterparty="+8801712345678")]
    out = investigate("I sent 3000 to wrong number", history)
    assert out["evidence_verdict"] == "inconsistent"
    assert out["relevant_transaction_id"] == "TX-MISMATCH"
    assert "amount_mismatch" in out["reason_codes"]


def test_no_signal_in_complaint_returns_insufficient():
    """Complaint has no amount/phone; investigator cannot infer a match."""
    history = [_entry()]
    out = investigate("My app is broken", history)
    # No usable signal => insufficient_data with reason_codes containing
    # at least "no_match".
    assert out["evidence_verdict"] == "insufficient_data"


def test_picks_best_score_among_multiple_entries():
    history = [
        _entry(transaction_id="TX-OLD", amount=100.0),
        _entry(transaction_id="TX-NEW", amount=3000.0,
               counterparty="+8801712345678"),
    ]
    out = investigate("I sent 3000 to +8801712345678 wrong number", history)
    assert out["relevant_transaction_id"] == "TX-NEW"
    assert out["evidence_verdict"] == "consistent"


def test_close_amount_within_one_percent_still_matches():
    history = [_entry(transaction_id="TX-CLOSE", amount=3010.0,
                      counterparty="+8801712345678")]
    out = investigate("I sent 3000 to +8801712345678 wrong number", history)
    # 10 BDT on 3000 is 0.33% — within 1% — should be consistent.
    assert out["evidence_verdict"] == "consistent"
    assert out["relevant_transaction_id"] == "TX-CLOSE"
    assert "amount_match_close" in out["reason_codes"]


def test_phone_counterparty_in_local_format_matches():
    """Local 01XXXXXXXXX form in complaint should match +880... counterparty."""
    history = [_entry(transaction_id="TX-LOCAL", amount=3000.0,
                      counterparty="+8801712345678")]
    out = investigate("I sent 3000 to 01712345678 wrong number", history)
    assert out["evidence_verdict"] == "consistent"
    assert out["relevant_transaction_id"] == "TX-LOCAL"


def test_payment_failed_with_completed_status_is_not_a_match():
    """`payment_failed` complaint with a completed entry should not be
    flagged consistent; status alignment should push score down."""
    history = [_entry(transaction_id="TX-OK", amount=3000.0, status="completed")]
    out = investigate("Payment failed but my balance was deducted 3000", history)
    # Either inconsistent or insufficient_data is acceptable — both are
    # non-consistent and force human review. We only require NOT consistent.
    assert out["evidence_verdict"] != "consistent"


def test_reason_codes_always_present():
    out = investigate("I sent 3000 to wrong number", [])
    assert isinstance(out["reason_codes"], list)
    assert len(out["reason_codes"]) >= 1
