"""Safety layer: scrub customer-facing strings and build final reply/next-action.

This module is the last line of defense against violating section 8 of the
problem statement. Any string that reaches the response is passed through
scrub() and rewritten to a safe default if it asks for credentials,
promises an unauthorized refund, or instructs the customer to contact a
suspicious third party.
"""

from __future__ import annotations

import os
import re
from typing import Optional

from templates import format_reply, get_template


# Regexes for forbidden content. Patterns are deliberately generous so we
# catch common phrasings ("send us your PIN", "share your otp", "tell us
# the password").
_FORBIDDEN_CREDENTIAL_REQUESTS = [
    r"\bsend\s+(?:us|me|over)?\s*(?:your|the)\s*(?:pin|otp|password|cvv|full\s*card\s*number|card\s*details)\b",
    r"\bshare\s+(?:us|me|over)?\s*(?:your|the)\s*(?:pin|otp|password|cvv|full\s*card\s*number|card\s*details)\b",
    r"\btell\s+(?:us|me)\s+(?:your|the)\s*(?:pin|otp|password|cvv|full\s*card\s*number|card\s*details)\b",
    r"\bprovide\s+(?:us|me|over)?\s*(?:your|the)\s*(?:pin|otp|password|cvv|full\s*card\s*number|card\s*details)\b",
    r"\bgive\s+(?:us|me)\s+(?:your|the)\s*(?:pin|otp|password|cvv|full\s*card\s*number|card\s*details)\b",
    r"\bverify\s+(?:your|the)\s*(?:pin|otp|password)\b",
    r"\bconfirm\s+(?:your|the)\s*(?:pin|otp|password)\b",
    r"\benter\s+(?:your|the)\s*(?:pin|otp|password|cvv)\b",
    r"\b(?:pin|otp|password|cvv)\s+(?:number|code|details)?\s+(?:is|should be|required)\b",
]

_FORBIDDEN_REFUND_PROMISES = [
    r"\bwe\s+will\s+refund\s+you\b",
    r"\bwe\s+will\s+reverse\s+(?:it|the\s+transaction|the\s+amount)\b",
    r"\bwe\s+will\s+return\s+(?:it|the\s+money|your\s+money|the\s+amount)\b",
    r"\bwe\s+will\s+unblock\s+(?:your\s+account|the\s+account)\b",
    r"\byour\s+refund\s+is\s+approved\b",
    r"\brefund\s+has\s+been\s+(?:approved|processed)\b",
    r"\brefund\s+will\s+be\s+(?:sent|processed)\s+(?:today|now|immediately)\b",
    r"\breversed\s+(?:already\s+)?(?:today|now|immediately)\b",
]

# Phone numbers and URLs in the customer_reply are treated as suspicious
# third-party contacts. Our own hotline / app URLs are whitelisted below.
_OFFICIAL_URL_WHITELIST = (
    "the official app",
    "the official hotline",
    "official channels",
    "official support channels",
    "official platform",
    "official merchant",
)

# Match +880... or 01... phone numbers, or any http(s) URL.
_THIRD_PARTY_CONTACT_RE = re.compile(
    r"(\+?880\s?1[3-9]\d{8}|01[3-9]\d{8}|https?://[^\s]+)"
)


_SAFE_REPLY_FALLBACK = (
    "Thank you for contacting us. We have recorded your message. Our "
    "support team will follow up through official channels. Please do "
    "not share any one-time or secret credentials with anyone."
)

_SAFE_NEXT_ACTION_FALLBACK = (
    "Route to the appropriate queue for manual review. Do not confirm "
    "any recovery action to the customer until verified."
)


def _has_match(text: str, patterns: list[str]) -> bool:
    if not text:
        return False
    return any(re.search(p, text, re.IGNORECASE) for p in patterns)


def _has_third_party_contact(text: str) -> bool:
    """Return True if text contains a phone number or non-whitelisted URL
    that the customer might be told to contact.
    """
    if not text:
        return False
    matches = _THIRD_PARTY_CONTACT_RE.findall(text)
    if not matches:
        return False
    # If every match is in the official whitelist context, allow it.
    lower = text.lower()
    for m in matches:
        if any(w in lower for w in _OFFICIAL_URL_WHITELIST):
            continue
        # If the string is a URL but the surrounding sentence is a
        # whitelist phrase, still allow. (The whitelist covers it.)
        return True
    return False


def scrub_customer_reply(text: str) -> str:
    """Return a string that is safe to send to a customer.

    If any forbidden content is found, the entire reply is replaced with
    a safe default. We replace whole rather than redact so we never
    produce a half-broken sentence.
    """
    if not text:
        return _SAFE_REPLY_FALLBACK
    if _has_match(text, _FORBIDDEN_CREDENTIAL_REQUESTS):
        return _SAFE_REPLY_FALLBACK
    if _has_match(text, _FORBIDDEN_REFUND_PROMISES):
        return _SAFE_REPLY_FALLBACK
    if _has_third_party_contact(text):
        return _SAFE_REPLY_FALLBACK
    return text


def scrub_next_action(text: str) -> str:
    """Return a safe recommended_next_action string.

    Next-action is internal-facing for support agents, so the rules are
    less strict than for customer_reply. We still disallow unconditional
    refund confirmations.
    """
    if not text:
        return _SAFE_NEXT_ACTION_FALLBACK
    if _has_match(text, _FORBIDDEN_REFUND_PROMISES):
        return _SAFE_NEXT_ACTION_FALLBACK
    return text


def high_value_threshold() -> float:
    """Read HIGH_VALUE_THRESHOLD from env (default 50,000 BDT)."""
    try:
        return float(os.getenv("HIGH_VALUE_THRESHOLD", "50000"))
    except ValueError:
        return 50000.0


def force_human_review(
    case_type: str,
    verdict: str,
    txn_amount: Optional[float],
    base_flag: bool,
) -> bool:
    """Decide whether human_review_required must be true regardless of
    the classifier's initial flag.

    Floor rules:
      * phishing_or_social_engineering -> always
      * wrong_transfer -> always
      * insufficient_data -> always
      * amount >= threshold -> always
      * inconsistent verdict -> always
    """
    if case_type in ("phishing_or_social_engineering", "wrong_transfer"):
        return True
    if verdict in ("inconsistent", "insufficient_data"):
        return True
    threshold = high_value_threshold()
    if txn_amount is not None and txn_amount >= threshold:
        return True
    return base_flag


def build_response_fields(
    case_type: str,
    verdict: str,
    txn_id: Optional[str],
    txn_amount: Optional[float],
    txn_counterparty: Optional[str],
    ticket_id: str,
    base_human_review: bool,
    agent_summary: str,
) -> dict:
    """Render the customer_reply and recommended_next_action from
    templates, then pass through the safety scrubber.
    """
    bundle = get_template(case_type)
    filled = format_reply(
        bundle,
        ticket_id=ticket_id,
        transaction_id=txn_id,
        counterparty=txn_counterparty,
        amount=txn_amount,
    )

    customer_reply = scrub_customer_reply(filled["customer_reply"])
    next_action = scrub_next_action(filled["recommended_next_action"])

    human_review = force_human_review(
        case_type=case_type,
        verdict=verdict,
        txn_amount=txn_amount,
        base_flag=base_human_review,
    )

    return {
        "agent_summary": agent_summary,
        "customer_reply": customer_reply,
        "recommended_next_action": next_action,
        "human_review_required": human_review,
    }