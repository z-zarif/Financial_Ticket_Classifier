"""Text normalization and entity extraction helpers.

All functions are deliberately simple, pure-Python, and dependency-free
so the service stays fast, deterministic, and immune to prompt injection
through the extraction layer.
"""

from __future__ import annotations

import re
from typing import Iterable

# Matches digit groups that are likely BDT amounts: 5000, 5,000, 12.50, 1,00,000.
# We capture the normalized digits (commas removed) so callers can compare easily.
_AMOUNT_RE = re.compile(
    r"(?<![\w.])((?:\d{1,3}(?:[,]\d{2,3})+)|(?:\d+\.\d+)|(?:\d+))(?:\s*(taka|tk|টাকা|bdt|BDT))?",
    re.IGNORECASE,
)

# Bangladeshi phone numbers in international (880...) or local (01...) formats.
_PHONE_RE = re.compile(
    r"(?<![\w])(\+?880\s?1[3-9]\d{8}|01[3-9]\d{8})",
)

# Time hints like "around 2pm", "at 14:08", "সন্ধ্যায়" (in the evening).
_TIME_HINT_RE = re.compile(
    r"(?i)\b(?:around|at|by|after|before)?\s*"
    r"((?:[01]?\d|2[0-3])\s*[:.]\s*[0-5]\d"
    r"|(?:[01]?\d|2[0-3])\s*(?:am|pm|a\.m\.|p\.m\.)?)"
)


def normalize(text: str) -> str:
    """Lowercase, collapse whitespace, and apply minimal Banglish transliteration.

    Does not attempt full Bangla script transliteration. We map only the
    common ASCII spellings we have observed in training tickets.
    """
    if not text:
        return ""

    s = text.lower()
    # Collapse all whitespace runs to single spaces.
    s = re.sub(r"\s+", " ", s).strip()

    # Common Banglish -> English keyword substitutions for the classifier.
    substitutions = {
        r"\bwrong number\b": "wrong number",
        r"\bwrong no\b": "wrong number",
        r"\bwrong account\b": "wrong account",
        r"\bwrong person\b": "wrong recipient",
        r"\bville number\b": "wrong number",
        r"\bbhul\b": "wrong",
        r"\bbhul number\b": "wrong number",
        r"\bbhul dite\b": "wrong",
        r"\btransfer\b": "transfer",
        r"\btransaction\b": "transaction",
        r"\bbalance kete niyeche\b": "balance deducted",
        r"\bbalance kata hoye geche\b": "balance deducted",
        r"\bbalance kata\b": "balance deducted",
        r"\btaka katse\b": "balance deducted",
        r"\btaka kete niyeche\b": "balance deducted",
        r"\bmoney back\b": "refund",
        r"\btaka ferot\b": "refund",
        r"\btaka pabo\b": "refund",
        r"\btaka pete chai\b": "refund",
        r"\botp\b": "otp",
        r"\bpin\b": "pin",
        r"\bpassword\b": "password",
        r"\bscam\b": "scam",
        r"\bscammer\b": "scam",
        r"\bfraud\b": "fraud",
        r"\bfake call\b": "suspicious call",
        r"\bscam call\b": "suspicious call",
    }
    for pattern, replacement in substitutions.items():
        s = re.sub(pattern, replacement, s)

    return s


def extract_amounts(text: str) -> list[float]:
    """Extract numeric amounts in BDT from free text.

    Returns values as floats. Empty list if nothing found.
    """
    out: list[float] = []
    for m in _AMOUNT_RE.finditer(text):
        raw = m.group(1)
        try:
            value = float(raw.replace(",", ""))
        except ValueError:
            continue
        if value <= 0:
            continue
        out.append(value)
    return out


def extract_phone_numbers(text: str) -> list[str]:
    """Extract Bangladeshi phone numbers in a normalized form (+880XXXXXXXXXX)."""
    out: list[str] = []
    for m in _PHONE_RE.finditer(text):
        digits = re.sub(r"\D", "", m.group(1))
        if digits.startswith("880"):
            out.append("+" + digits)
        elif digits.startswith("01") and len(digits) == 11:
            out.append("+880" + digits[1:])
        elif len(digits) == 10 and digits.startswith("1"):
            out.append("+880" + digits)
    return out


def extract_time_hint(text: str) -> str | None:
    """Return the first detected time hint (e.g. '2pm', '14:08') or None."""
    m = _TIME_HINT_RE.search(text)
    if not m:
        return None
    return m.group(1).strip()


def contains_any(text: str, needles: Iterable[str]) -> bool:
    """Case-insensitive substring check against any needle."""
    if not text:
        return False
    return any(n in text for n in needles if n)