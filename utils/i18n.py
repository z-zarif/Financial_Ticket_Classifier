"""Keyword packs grouped by case_type, with English + Banglish spellings.

These are matched against the *normalized* complaint text produced by
utils.text.normalize, so we don't need to repeat case-insensitivity
or Banglish substitutions here.
"""

from __future__ import annotations

from typing import TypedDict


class KeywordPack(TypedDict):
    case_type: str
    severity: str
    department: str
    human_review: bool
    keywords: list[str]


# Order matters: the first matching case_type wins. Place higher-risk
# categories (phishing, wrong_transfer) before lower-risk ones (refund).
KEYWORD_PACKS: list[KeywordPack] = [
    {
        "case_type": "phishing_or_social_engineering",
        "severity": "critical",
        "department": "fraud_risk",
        "human_review": True,
        "keywords": [
            "otp",
            "pin",
            "password",
            "verification code",
            "security code",
            "cvv",
            "card number",
            "asked for otp",
            "asked for pin",
            "asked for password",
            "suspicious call",
            "fake call",
            "scam call",
            "scam",
            "scammer",
            "fraud",
            "phishing",
            "social engineering",
            "someone is asking for",
            "someone called me asking",
            "lost money to a scam",
            "impersonator",
            "fake agent",
            "impersonation",
        ],
    },
    {
        "case_type": "wrong_transfer",
        "severity": "high",
        "department": "dispute_resolution",
        "human_review": True,
        "keywords": [
            "wrong number",
            "wrong no",
            "wrong account",
            "wrong person",
            "wrong recipient",
            "wrong mobile",
            "wrong phone",
            "sent to wrong",
            "transferred to wrong",
            "money sent to wrong",
            "sent money to wrong",
            "wrong transfer",
            "incorrect recipient",
            "mistakenly sent",
            "accidentally sent",
        ],
    },
    {
        "case_type": "agent_cash_in_issue",
        "severity": "high",
        "department": "agent_operations",
        "human_review": True,
        "keywords": [
            "agent did not deposit",
            "agent didn't deposit",
            "agent did not give money",
            "cash in not received",
            "cash-in not received",
            "cash in missing",
            "agent did not pay",
            "agent did not add money",
            "agent did not transfer",
            "agent did not push",
            "agent pocketed",
            "agent took money",
            "agent kept money",
        ],
    },
    {
        "case_type": "merchant_settlement_delay",
        "severity": "high",
        "department": "merchant_operations",
        "human_review": True,
        "keywords": [
            "merchant payment not received",
            "settlement not received",
            "settlement delay",
            "settlement pending",
            "merchant settlement",
            "merchant payout",
            "merchant dues",
            "store settlement",
            "shop settlement",
            "settlement not credited",
        ],
    },
    {
        "case_type": "duplicate_payment",
        "severity": "high",
        "department": "payments_ops",
        "human_review": True,
        "keywords": [
            "charged twice",
            "charged two times",
            "double charged",
            "duplicate charge",
            "duplicate payment",
            "same payment twice",
            "two transactions same amount",
            "deducted twice",
            "deducted two times",
        ],
    },
    {
        "case_type": "payment_failed",
        "severity": "high",
        "department": "payments_ops",
        "human_review": True,
        "keywords": [
            "payment failed",
            "transaction failed",
            "failed transaction",
            "failed payment",
            "balance deducted",
            "money deducted",
            "amount deducted but not received",
            "amount deducted",
            "deducted but failed",
            "did not receive",
            "did not get",
            "but balance deducted",
            "but money deducted",
            "taka katse",
            "taka kete niyeche",
            "balance kata",
        ],
    },
    {
        "case_type": "refund_request",
        "severity": "low",
        "department": "customer_support",
        "human_review": False,
        "keywords": [
            "refund",
            "refund request",
            "money back",
            "return money",
            "return my money",
            "cancel transaction",
            "cancel payment",
            "want my money back",
            "please refund",
            "taka ferot",
            "taka pabo",
            "taka pete chai",
        ],
    },
]