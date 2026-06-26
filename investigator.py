"""Investigator module: match the complaint to a transaction in the
provided history and decide the evidence verdict.

Public function:
    investigate(complaint: str, history: list[dict]) -> InvestigationResult

Where InvestigationResult is a dict with:
    relevant_transaction_id: Optional[str]
    evidence_verdict: "consistent" | "inconsistent" | "insufficient_data"
    reason_codes: list[str]
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from utils.text import (
    extract_amounts,
    extract_phone_numbers,
    extract_time_hint,
    normalize,
)


# History entries with a "completed" status cannot contradict a "failed"
# complaint. Status mismatches are treated as separate signals in the
# scoring rather than as a hard contradiction by themselves.
_INDICATIVE_STATUSES_FOR_COMPLAINT = {
    "wrong_transfer": {"completed"},
    "payment_failed": {"failed", "pending"},
    "refund_request": {"completed", "failed", "reversed"},
    "duplicate_payment": {"completed"},
    "merchant_settlement_delay": {"pending", "completed", "failed"},
    "agent_cash_in_issue": {"completed", "pending", "failed"},
    "phishing_or_social_engineering": set(),
    "other": {"completed", "failed", "pending", "reversed"},
}


def _norm_counterparty(value: str) -> str:
    """Normalize counterparty strings so phone numbers compare consistently."""
    if not value:
        return ""
    digits = "".join(ch for ch in value if ch.isdigit())
    if digits.startswith("880") and len(digits) >= 13:
        return "+" + digits[:13]
    if digits.startswith("01") and len(digits) == 11:
        return "+880" + digits[1:]
    if len(digits) == 10 and digits.startswith("1"):
        return "+880" + digits
    return value.strip().lower()


def _parse_iso(ts: str) -> Optional[datetime]:
    if not ts:
        return None
    try:
        # Tolerate trailing Z.
        if ts.endswith("Z"):
            ts = ts[:-1] + "+00:00"
        return datetime.fromisoformat(ts)
    except ValueError:
        return None


def _status_matches(case_hint: str, status: str) -> bool:
    expected = _INDICATIVE_STATUSES_FOR_COMPLAINT.get(case_hint, set())
    if not expected:
        return True
    return status in expected


def _score_entry(
    entry: dict,
    complaint_amounts: list[float],
    complaint_phones: list[str],
    complaint_time: Optional[str],
) -> tuple[float, list[str]]:
    """Return (score, reason_codes) for one history entry.

    Higher score = stronger match. A negative score indicates contradiction.
    """
    score = 0.0
    reasons: list[str] = []

    entry_amount = entry.get("amount")
    entry_counterparty = entry.get("counterparty", "")
    entry_status = entry.get("status", "")
    entry_type = entry.get("type", "")

    # --- Amount matching -------------------------------------------------
    if complaint_amounts and entry_amount is not None:
        target = float(entry_amount)
        best = min(complaint_amounts, key=lambda a: abs(a - target))
        diff = abs(best - target)
        if diff == 0:
            score += 5.0
            reasons.append("amount_match_exact")
        elif diff <= max(1.0, target * 0.01):
            score += 3.0
            reasons.append("amount_match_close")
        else:
            # Amount mismatch — strong negative signal unless there is
            # an exact duplicate in complaint_amounts elsewhere.
            score -= 4.0
            reasons.append("amount_mismatch")

    # --- Counterparty matching -------------------------------------------
    if complaint_phones:
        target_phone = _norm_counterparty(entry_counterparty)
        if target_phone and any(p == target_phone for p in complaint_phones):
            score += 4.0
            reasons.append("counterparty_match")
        elif target_phone:
            # Complaint mentions *a* phone but this isn't it.
            score -= 1.0

    # --- Type sanity (transfer complaint should match a transfer history) --
    # We do not have case_hint here; type sanity is handled in investigate().
    _ = entry_type

    # --- Status alignment is evaluated outside, using case_hint ----------
    _ = entry_status

    # --- Time proximity --------------------------------------------------
    complaint_dt = _parse_time_hint(complaint_time)
    entry_dt = _parse_iso(entry.get("timestamp", ""))
    if complaint_dt and entry_dt:
        delta = abs((entry_dt - complaint_dt).total_seconds())
        if delta <= 60 * 60:
            score += 1.0
            reasons.append("time_within_1h")
        elif delta <= 60 * 60 * 6:
            score += 0.3
        elif delta <= 60 * 60 * 24:
            score += 0.1

    return score, reasons


def _parse_time_hint(hint: Optional[str]) -> Optional[datetime]:
    if not hint:
        return None
    hint = hint.lower().replace(" ", "")
    # Try HH:MM first.
    for fmt in ("%H:%M", "%H.%M"):
        try:
            return datetime.strptime(hint, fmt)
        except ValueError:
            continue
    # Try 2pm / 2am style.
    import re

    m = re.match(r"^(\d{1,2})(am|pm|a\.m\.|p\.m\.)$", hint)
    if m:
        hour = int(m.group(1)) % 12
        if "p" in m.group(2):
            hour += 12
        return datetime.strptime(f"{hour:02d}:00", "%H:%M")
    return None


def _guess_case_hint(normalized: str) -> str:
    """Crude case-type hint from the complaint text, used only to decide
    whether a status mismatch is a contradiction.
    """
    if any(k in normalized for k in ("wrong number", "wrong account", "wrong recipient",
                                     "mistakenly sent", "accidentally sent",
                                     "sent to wrong", "transferred to wrong")):
        return "wrong_transfer"
    if any(k in normalized for k in ("payment failed", "transaction failed", "balance deducted",
                                     "money deducted", "did not receive", "but balance",
                                     "but money", "taka kete niyeche", "taka katse")):
        return "payment_failed"
    if any(k in normalized for k in ("refund", "money back", "return money", "taka ferot")):
        return "refund_request"
    if any(k in normalized for k in ("charged twice", "double charged", "duplicate")):
        return "duplicate_payment"
    if any(k in normalized for k in ("settlement", "merchant payout")):
        return "merchant_settlement_delay"
    if any(k in normalized for k in ("agent did not", "cash in not received", "agent pocketed",
                                     "agent took money", "agent kept money")):
        return "agent_cash_in_issue"
    if any(k in normalized for k in ("otp", "pin", "password", "scam", "fraud", "phishing",
                                     "suspicious call", "fake call", "impersonator")):
        return "phishing_or_social_engineering"
    return "other"


def investigate(complaint: str, history: list[dict]) -> dict:
    """Match a complaint against a list of transaction dicts.

    Returns a dict with `relevant_transaction_id`, `evidence_verdict`,
    and `reason_codes`. The verdict is one of:
        - "consistent" — the best-matching entry supports the complaint
        - "inconsistent" — the best entry contradicts the complaint
        - "insufficient_data" — nothing usable in the history
    """
    normalized = normalize(complaint)
    complaint_amounts = extract_amounts(complaint)
    complaint_phones = extract_phone_numbers(complaint)
    complaint_time = extract_time_hint(complaint)

    if not history:
        return {
            "relevant_transaction_id": None,
            "evidence_verdict": "insufficient_data",
            "reason_codes": ["empty_history"],
        }

    case_hint = _guess_case_hint(normalized)

    # Score every entry, then pick the best.
    scored: list[tuple[float, list[str], dict]] = []
    for entry in history:
        base_score, reasons = _score_entry(
            entry, complaint_amounts, complaint_phones, complaint_time
        )

        # Status alignment is a soft signal for most case_types, but for
        # "payment_failed" a "completed" entry is a direct contradiction —
        # weight it heavily enough to flip the verdict.
        status = entry.get("status", "")
        if status and not _status_matches(case_hint, status):
            if case_hint == "payment_failed":
                base_score -= 6.0
                reasons.append("status_contradicts_payment_failed")
            elif case_hint == "wrong_transfer":
                base_score -= 1.0
            else:
                base_score -= 0.5

        scored.append((base_score, reasons, entry))

    if not scored:
        return {
            "relevant_transaction_id": None,
            "evidence_verdict": "insufficient_data",
            "reason_codes": ["empty_history"],
        }

    scored.sort(key=lambda x: x[0], reverse=True)
    best_score, best_reasons, best_entry = scored[0]
    second_score = scored[1][0] if len(scored) > 1 else -999

    # The complaint had no signal at all (no amount, no phone, no time) AND
    # no entry produced a positive match score — nothing to verify.
    has_complaint_signal = bool(complaint_amounts or complaint_phones or complaint_time)
    if not has_complaint_signal and best_score <= 0:
        return {
            "relevant_transaction_id": None,
            "evidence_verdict": "insufficient_data",
            "reason_codes": ["no_match"] + best_reasons,
        }

    # Complaint had no usable signal but an entry exists — still can't verify.
    if not has_complaint_signal:
        return {
            "relevant_transaction_id": None,
            "evidence_verdict": "insufficient_data",
            "reason_codes": ["no_signal_in_complaint"] + best_reasons,
        }

    # Distinct contradiction: a clear amount_mismatch that outweighs any
    # counterparty/time hint.
    if "amount_mismatch" in best_reasons and best_score < 1.5:
        return {
            "relevant_transaction_id": best_entry.get("transaction_id"),
            "evidence_verdict": "inconsistent",
            "reason_codes": best_reasons + ["amount_contradicts"],
        }

    # Score is dominated by a mismatch signal with no positive supporting
    # evidence — still inconsistent.
    positives = [r for r in best_reasons if "match" in r or "within" in r]
    negatives = [r for r in best_reasons if "mismatch" in r or "contradict" in r]
    if negatives and not positives:
        return {
            "relevant_transaction_id": best_entry.get("transaction_id"),
            "evidence_verdict": "inconsistent",
            "reason_codes": best_reasons + ["contradictory_only"],
        }

    # A status contradiction for payment_failed is a direct contradiction
    # even when an amount matches: a "completed" entry cannot back up a
    # "payment failed" complaint.
    if "status_contradicts_payment_failed" in best_reasons:
        return {
            "relevant_transaction_id": best_entry.get("transaction_id"),
            "evidence_verdict": "inconsistent",
            "reason_codes": best_reasons + ["status_contradicts_complaint"],
        }

    # Best entry is well ahead of the runner-up and is consistent.
    verdict = "consistent"
    if best_score - second_score < 1.0:
        verdict = "insufficient_data"
        best_reasons = best_reasons + ["ambiguous_match"]

    return {
        "relevant_transaction_id": best_entry.get("transaction_id"),
        "evidence_verdict": verdict,
        "reason_codes": best_reasons,
    }