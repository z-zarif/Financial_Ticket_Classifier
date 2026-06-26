"""Unit tests for the safety layer (section 8 of the problem statement).

Covers:
    * credential-request scrubber
    * unauthorized refund-promise scrubber
    * third-party-contact detection (phone + URL)
    * human_review_required floor rules
    * template filling never produces half-blank text
"""

from __future__ import annotations

import os

import pytest

from safety import (
    build_response_fields,
    force_human_review,
    scrub_customer_reply,
    scrub_next_action,
)


# --------------------------------------------------------------------------
# scrub_customer_reply
# --------------------------------------------------------------------------


def test_clean_text_passes_through():
    safe = "Thank you. We will follow up through the official app."
    assert scrub_customer_reply(safe) == safe


def test_pin_request_is_scrubbed_to_fallback():
    bad = "Please send us your PIN to verify your account."
    out = scrub_customer_reply(bad)
    assert "PIN" not in out
    assert "do not share" in out.lower()


def test_otp_request_is_scrubbed_to_fallback():
    bad = "Please share your OTP code so we can confirm."
    out = scrub_customer_reply(bad)
    assert "OTP" not in out
    assert "do not share" in out.lower()


def test_password_request_is_scrubbed_to_fallback():
    bad = "Tell us your password to verify."
    out = scrub_customer_reply(bad)
    assert "password" not in out.lower() or "do not share" in out.lower()


def test_unauthorized_refund_promise_is_scrubbed():
    bad = "We will refund you immediately."
    out = scrub_customer_reply(bad)
    assert "we will refund" not in out.lower()
    assert "do not share" in out.lower()


def test_refund_already_processed_is_scrubbed():
    bad = "Your refund has been approved and will be processed today."
    out = scrub_customer_reply(bad)
    assert "approved" not in out.lower() or "do not share" in out.lower()


def test_third_party_phone_in_reply_is_scrubbed():
    bad = "Please contact 01712345678 to verify your account."
    out = scrub_customer_reply(bad)
    assert "01712345678" not in out
    assert "do not share" in out.lower()


def test_third_party_url_in_reply_is_scrubbed():
    bad = "Visit https://sketchy-site.example to recover your account."
    out = scrub_customer_reply(bad)
    assert "https://sketchy-site.example" not in out
    assert "do not share" in out.lower()


def test_official_app_phrase_does_not_trigger_scrubber():
    safe = "Please use the official app for any account changes."
    assert scrub_customer_reply(safe) == safe


def test_official_hotline_phrase_does_not_trigger_scrubber():
    safe = "Call the official hotline if you need more help."
    assert scrub_customer_reply(safe) == safe


def test_empty_text_returns_safe_fallback():
    out = scrub_customer_reply("")
    assert "do not share" in out.lower()


# --------------------------------------------------------------------------
# scrub_next_action (internal-facing — only refund promises are blocked)
# --------------------------------------------------------------------------


def test_next_action_blocks_unauthorized_refund_promise():
    bad = "We will refund you today."
    out = scrub_next_action(bad)
    assert "we will refund" not in out.lower()


def test_next_action_allows_normal_routing_text():
    ok = "Route to dispute_resolution queue for manual review."
    assert scrub_next_action(ok) == ok


# --------------------------------------------------------------------------
# force_human_review
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "case_type,verdict,amount,base,expected",
    [
        ("phishing_or_social_engineering", "consistent", 100.0, False, True),
        ("wrong_transfer", "consistent", 100.0, False, True),
        ("payment_failed", "inconsistent", 100.0, False, True),
        ("payment_failed", "insufficient_data", 100.0, False, True),
        ("refund_request", "consistent", 100000.0, False, True),  # high value
        ("refund_request", "consistent", 100.0, False, False),
        ("refund_request", "consistent", 100.0, True, True),  # base override
    ],
)
def test_force_human_review_floors(case_type, verdict, amount, base, expected):
    assert force_human_review(case_type, verdict, amount, base) is expected


def test_high_value_threshold_respects_env(monkeypatch):
    monkeypatch.setenv("HIGH_VALUE_THRESHOLD", "100")
    # 150 BDT should now force review even for an otherwise-routine case.
    assert (
        force_human_review("refund_request", "consistent", 150.0, False)
        is True
    )


# --------------------------------------------------------------------------
# build_response_fields (integration with templates)
# --------------------------------------------------------------------------


def test_build_response_fields_renders_without_missing_placeholders():
    out = build_response_fields(
        case_type="wrong_transfer",
        verdict="consistent",
        txn_id="TX-1",
        txn_amount=3000.0,
        txn_counterparty="+8801712345678",
        ticket_id="T-1",
        base_human_review=False,
        agent_summary="Customer reports wrong transfer.",
    )
    # No raw placeholder should survive into the rendered reply.
    assert "{ticket_id}" not in out["customer_reply"]
    assert "{transaction_id}" not in out["customer_reply"]
    assert out["human_review_required"] is True  # wrong_transfer floor


def test_build_response_fields_never_returns_empty_strings():
    """Even if every field is None, output strings must be non-empty."""
    out = build_response_fields(
        case_type="other",
        verdict="insufficient_data",
        txn_id=None,
        txn_amount=None,
        txn_counterparty=None,
        ticket_id="T-X",
        base_human_review=False,
        agent_summary="",
    )
    assert out["customer_reply"].strip()
    assert out["recommended_next_action"].strip()
