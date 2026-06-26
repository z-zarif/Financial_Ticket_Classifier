import re

def classify_ticket(message: str):
    text = message.lower()

    case_type = "other"
    severity = "low"
    department = "customer_support"
    confidence = 0.6
    human_review_required = False

    phishing_keywords = [
        "otp",
        "pin",
        "password",
        "verification code",
        "scam",
        "fraud",
        "suspicious call",
    ]

    wrong_transfer_keywords = [
        "wrong number",
        "wrong account",
        "wrong recipient",
        "sent money to wrong",
    ]

    payment_failed_keywords = [
        "payment failed",
        "transaction failed",
        "balance deducted",
        "money deducted",
    ]

    refund_keywords = [
        "refund",
        "money back",
        "return money",
        "cancel transaction",
    ]

    if any(k in text for k in phishing_keywords):
        case_type = "phishing_or_social_engineering"
        severity = "critical"
        department = "fraud_risk"
        confidence = 0.95
        human_review_required = True

    elif any(k in text for k in wrong_transfer_keywords):
        case_type = "wrong_transfer"
        severity = "high"
        department = "dispute_resolution"
        confidence = 0.90
        human_review_required = True

    elif any(k in text for k in payment_failed_keywords):
        case_type = "payment_failed"
        severity = "high"
        department = "payments_ops"
        confidence = 0.90
        human_review_required = False

    elif any(k in text for k in refund_keywords):
        case_type = "refund_request"
        severity = "low"
        department = "customer_support"
        confidence = 0.85
        human_review_required = False

    summary = generate_summary(message, case_type)

    return {
        "case_type": case_type,
        "severity": severity,
        "department": department,
        "agent_summary": summary,
        "human_review_required": human_review_required,
        "confidence": confidence,
    }


def generate_summary(message: str, case_type: str):
    if case_type == "wrong_transfer":
        return "Customer reports sending funds to an incorrect recipient and requests assistance recovering the money."

    if case_type == "payment_failed":
        return "Customer reports a failed transaction and possible balance deduction."

    if case_type == "refund_request":
        return "Customer requests a refund for a recent transaction."

    if case_type == "phishing_or_social_engineering":
        return "Customer reports suspicious activity involving requests for sensitive account information."

    return "Customer reports an issue that requires further investigation."