"""Classifier module: pick case_type / severity / department / confidence.

Pure rule-based logic over the normalized complaint text plus the
investigator's evidence verdict. The verdict biases severity and routing
without ever overriding the safety floor (phishing always wins, ambiguous
data always escalates).
"""

from __future__ import annotations

from typing import Optional

from utils.text import contains_any, normalize
from utils.i18n import KEYWORD_PACKS


# When the complaint carries strong evidence of a contested case, the
# department jumps from customer_support -> dispute_resolution.
_CONTESTED_CASE_TYPES = {
    "wrong_transfer",
    "payment_failed",
    "duplicate_payment",
    "refund_request",  # becomes contested when verdict says it didn't happen
}


def classify(
    complaint: str,
    verdict: str,
    txn_id: Optional[str],
) -> dict:
    """Return a dict with case_type, severity, department, confidence,
    human_review_required, and reason_codes.

    Severity and department may be adjusted upward based on the
    investigator's verdict, but they are never adjusted downward for
    safety reasons.
    """
    text = normalize(complaint)

    # 1. Find the first matching case_type via ordered keyword packs.
    case_type = "other"
    severity = "low"
    department = "customer_support"
    human_review = False
    base_confidence = 0.55
    matched_keywords: list[str] = []
    matched_pack = None

    for pack in KEYWORD_PACKS:
        hits = [k for k in pack["keywords"] if k in text]
        if hits:
            case_type = pack["case_type"]
            severity = pack["severity"]
            department = pack["department"]
            human_review = bool(pack["human_review"])
            base_confidence = 0.85
            matched_keywords = hits
            matched_pack = pack
            break

    reason_codes: list[str] = list(matched_keywords)

    # 2. Severity and department adjustments from evidence verdict.
    if verdict == "inconsistent":
        # Customer's claim is contradicted by their own data. Treat as
        # contested and require human review.
        human_review = True
        reason_codes.append("evidence_inconsistent")
        if case_type == "refund_request":
            severity = "medium"
        else:
            severity = "high" if severity in ("low", "medium") else severity
        if case_type in _CONTESTED_CASE_TYPES:
            department = "dispute_resolution"
        base_confidence = max(base_confidence, 0.7)
    elif verdict == "insufficient_data":
        if case_type == "other":
            severity = "medium"
        else:
            severity = max_severity(severity, "medium")
        human_review = True
        reason_codes.append("evidence_insufficient")
        base_confidence = max(0.4, base_confidence - 0.15)
    elif verdict == "consistent" and txn_id:
        reason_codes.append("evidence_consistent")
        base_confidence = min(0.95, base_confidence + 0.05)

    # 3. Floor rules: phishing is always critical + fraud_risk + human_review.
    if case_type == "phishing_or_social_engineering":
        severity = "critical"
        department = "fraud_risk"
        human_review = True
        reason_codes.append("phishing_floor")

    # 4. Generic safety floors for any high-stakes case.
    if severity in ("high", "critical"):
        human_review = True

    return {
        "case_type": case_type,
        "severity": severity,
        "department": department,
        "confidence": round(base_confidence, 2),
        "human_review_required": human_review,
        "reason_codes": reason_codes,
    }


_SEVERITY_ORDER = {"low": 0, "medium": 1, "high": 2, "critical": 3}


def max_severity(a: str, b: str) -> str:
    return a if _SEVERITY_ORDER.get(a, 0) >= _SEVERITY_ORDER.get(b, 0) else b
