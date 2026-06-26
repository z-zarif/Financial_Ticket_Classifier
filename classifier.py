import re
from datetime import datetime, timedelta
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
duplicate_keywords=[
    "twice","duplicate","deducted twice","charged twice", "two times"
]
settlement_keywords=[
    "settlement", "settled", "merchant", "sales"
]
agent_cashin_keywords=[
    "cash in", "cash-in", "agent"
]

VAGUE_PATTERNS = [
    r"^something is wrong",
    r"check my account$",
    r"please help$",
]

REPLY_TEMPLATES = {
    "en": {
        "dispute": "We have noted your concern about transaction {txn}. Please do not share your PIN or OTP with anyone. Our dispute team will review the case and contact you through official support channels.",
        "dispute_inconsistent": "We have received your request regarding transaction {txn}. Please do not share your PIN or OTP with anyone. Our dispute team will review the case carefully and contact you through official support channels.",
        "payments_ops": "We have noted that transaction {txn} may have caused an unexpected balance deduction. Our payments team will review the case and any eligible amount will be returned through official channels. Please do not share your PIN or OTP with anyone.",
        "duplicate": "We have noted the possible duplicate payment for transaction {txn}. Our payments team will verify with the biller and any eligible amount will be returned through official channels. Please do not share your PIN or OTP with anyone.",
        "refund": "Thank you for reaching out. Refunds for completed merchant payments depend on the merchant's own policy. We recommend contacting the merchant directly. If you need help reaching them, please reply and we will guide you. Please do not share your PIN or OTP with anyone.",
        "phishing": "Thank you for reaching out before sharing any information. We never ask for your PIN, OTP, or password under any circumstances. Please do not share these with anyone, even if they claim to be from us. Our fraud team has been notified of this incident.",
        "vague": "Thank you for reaching out. To help you faster, please share the transaction ID, the amount involved, and a short description of what went wrong. Please do not share your PIN or OTP with anyone.",
        "ambiguous": "Thank you for reaching out. We see multiple matching transactions. Could you share more identifying details (such as the recipient's number) so we can identify the right transaction? Please do not share your PIN or OTP with anyone.",
        "agent_ops": "We have noted your concern about transaction {txn}. Our agent operations team will verify this quickly and update you through official channels. Please do not share your PIN or OTP with anyone.",
        "merchant_ops": "We have noted your concern about settlement {txn}. Our merchant operations team will check the batch status and update you on the expected settlement time through official channels.",
        "other": "Thank you for reaching out. Our support team will review your case and update you through official channels. Please do not share your PIN or OTP with anyone.",
    },
    "bn": {
        "agent_ops": "আপনার লেনদেন {txn} এর বিষয়ে আমরা অবগত হয়েছি। আমাদের এজেন্ট অপারেশন্স দল এটি দ্রুত যাচাই করবে এবং অফিসিয়াল চ্যানেলে আপনাকে জানাবে। অনুগ্রহ করে কারো সাথে আপনার পিন বা ওটিপি শেয়ার করবেন না।",
        "other": "আপনার অভিযোগটি আমরা পেয়েছি। অফিসিয়াল চ্যানেলে আমরা আপনাকে জানাবো। অনুগ্রহ করে কারো সাথে আপনার পিন বা ওটিপি শেয়ার করবেন না।",
    },
}

def _reply(lang: str, key: str, txn: str = None) -> str:
    lang = lang if lang in REPLY_TEMPLATES else "en"
    templates = REPLY_TEMPLATES[lang]
    template = templates.get(key) or REPLY_TEMPLATES["en"].get(key, REPLY_TEMPLATES["en"]["other"])
    return template.format(txn=txn) if txn else template

def _extract_amount(text:str):
      match = re.search(r"(\d{2,7})\s*(?:taka|tk|bdt)?", text)
      return int(match.group(1)) if match else None


def find_matching_transactions(text:str, transactions:list):
    amount=_extract_amount(text)
    if amount is None or not transactions:
        return []
    return [t for t in transactions if t.get(amount)==amount]



def find_duplicate_pair(transactions: list):
    """Find two completed payments of identical amount/counterparty close in time."""
    payments = [t for t in transactions if t.get("type") == "payment" and t.get("status") == "completed"]
    payments.sort(key=lambda t: t["timestamp"])
    for i in range(len(payments) - 1):
        a, b = payments[i], payments[i + 1]
        if a["amount"] == b["amount"] and a["counterparty"] == b["counterparty"]:
            try:
                t1 = datetime.fromisoformat(a["timestamp"].replace("Z", "+00:00"))
                t2 = datetime.fromisoformat(b["timestamp"].replace("Z", "+00:00"))
                if abs((t2 - t1).total_seconds()) <= 300:
                    return b  # the later one is the suspected duplicate
            except Exception:
                continue
    return None


def is_vague(text: str) -> bool:
    if len(text.strip()) < 40 and not re.search(r"\d", text):
        return True
    return any(re.search(p, text) for p in VAGUE_PATTERNS)



def classify_ticket(ticket: dict) -> dict:
    complaint = ticket.get("complaint", "")
    text = complaint.lower()
    lang = ticket.get("language", "en")
    user_type = ticket.get("user_type", "customer")
    transactions = ticket.get("transaction_history", []) or []
    ticket_id = ticket.get("ticket_id")

    relevant_txn = None
    evidence_verdict = "insufficient_data"
    confidence = 0.6
    human_review_required = False
    reason_codes = []

    
   
    if any(k in text for k in phishing_keywords) and ("call" in text or "ask" in text or "share" in text or "otp" in text):
        case_type = "phishing_or_social_engineering"
        severity = "critical"
        department = "fraud_risk"
        confidence = 0.95
        human_review_required = True
        reason_codes = ["phishing", "credential_protection", "critical_escalation"]
        summary = "Customer reports a suspicious request for sensitive credentials (PIN/OTP/password), a likely social engineering attempt."
        reply = _reply(lang, "phishing")

    elif is_vague(text) and not find_matching_transactions(text, transactions):
        case_type = "other"
        severity = "low"
        department = "customer_support"
        confidence = 0.6
        human_review_required = False
        reason_codes = ["vague_complaint", "needs_clarification"]
        summary = "Customer reports a vague concern without specifying transaction, amount, or issue. Insufficient detail to identify any relevant transaction."
        reply = _reply(lang, "vague")
        
    elif any(k in text for k in duplicate_keywords):
        dup = find_duplicate_pair(transactions)
        if dup:
            case_type = "duplicate_payment"
            severity = "high"
            department = "payments_ops"
            relevant_txn = dup["transaction_id"]
            evidence_verdict = "consistent"
            confidence = 0.93
            human_review_required = True
            reason_codes = ["duplicate_payment", "biller_verification_required"]
            summary = f"Customer reports a duplicate payment. Two matching completed payments were found close together in time; {relevant_txn} is the suspected duplicate."
            reply = _reply(lang, "duplicate", relevant_txn)
        else:
            case_type = "duplicate_payment"
            severity = "medium"
            department = "payments_ops"
            evidence_verdict = "insufficient_data"
            confidence = 0.5
            human_review_required = True
            reason_codes = ["duplicate_payment_claim", "no_matching_pair_found"]
            summary = "Customer claims a duplicate payment, but no matching pair of identical transactions was found in history."
            reply = _reply(lang, "vague")

    # --- Merchant settlement delay ---
    elif user_type == "merchant" and any(k in text for k in settlement_keywords):
        matches = [t for t in transactions if t.get("type") == "settlement"]
        case_type = "merchant_settlement_delay"
        severity = "medium"
        department = "merchant_operations"
        if matches:
            relevant_txn = matches[0]["transaction_id"]
            evidence_verdict = "consistent"
            confidence = 0.92
        else:
            confidence = 0.55
        human_review_required = False
        reason_codes = ["merchant_settlement", "delay", "pending"]
        summary = "Merchant reports a settlement delay beyond the expected window."
        reply = _reply(lang, "merchant_ops", relevant_txn)

    # --- Agent cash-in issue ---
    elif any(k in text for k in agent_cashin_keywords):
        matches = [t for t in transactions if t.get("type") == "cash_in"]
        case_type = "agent_cash_in_issue"
        severity = "high"
        department = "agent_operations"
        if matches:
            relevant_txn = matches[0]["transaction_id"]
            evidence_verdict = "consistent"
            confidence = 0.88
        else:
            confidence = 0.55
        human_review_required = True
        reason_codes = ["agent_cash_in", "pending_transaction", "agent_ops"]
        summary = "Customer reports a cash-in via an agent that has not reflected in their balance."
        reply = _reply(lang, "agent_ops", relevant_txn)

    # --- Wrong transfer ---
    elif any(k in text for k in wrong_transfer_keywords):
        case_type = "wrong_transfer"
        department = "dispute_resolution"
        matches = find_matching_transactions(text, transactions)

        if len(matches) == 1:
            relevant_txn = matches[0]["transaction_id"]
            counterparty = matches[0]["counterparty"]
            prior = [
                t for t in transactions
                if t.get("counterparty") == counterparty and t["transaction_id"] != relevant_txn
            ]
            if prior:
                evidence_verdict = "inconsistent"
                severity = "medium"
                confidence = 0.75
                reason_codes = ["wrong_transfer_claim", "established_recipient_pattern", "evidence_inconsistent"]
                summary = (f"Customer claims {relevant_txn} was a wrong transfer, but transaction history "
                           f"shows prior transfers to the same counterparty, suggesting an established recipient.")
                reply = _reply(lang, "dispute_inconsistent", relevant_txn)
            else:
                evidence_verdict = "consistent"
                severity = "high"
                confidence = 0.9
                reason_codes = ["wrong_transfer", "transaction_match", "dispute_initiated"]
                summary = f"Customer reports sending funds via {relevant_txn} to an incorrect recipient."
                reply = _reply(lang, "dispute", relevant_txn)
            human_review_required = True

        elif len(matches) > 1:
            severity = "medium"
            confidence = 0.65
            human_review_required = False
            reason_codes = ["ambiguous_match", "needs_clarification"]
            summary = "Customer reports a wrong transfer, but multiple transactions match the stated amount. Cannot determine the correct one without further input."
            reply = _reply(lang, "ambiguous")
        else:
            severity = "medium"
            confidence = 0.5
            human_review_required = True
            reason_codes = ["wrong_transfer_claim", "no_matching_transaction"]
            summary = "Customer reports a wrong transfer, but no matching transaction was found in history."
            reply = _reply(lang, "dispute_inconsistent")

    # --- Payment failed ---
    elif any(k in text for k in payment_failed_keywords):
        case_type = "payment_failed"
        severity = "high"
        department = "payments_ops"
        matches = [t for t in transactions if t.get("status") == "failed"]
        if matches:
            relevant_txn = matches[0]["transaction_id"]
            evidence_verdict = "consistent"
            confidence = 0.9
        else:
            confidence = 0.55
        human_review_required = False
        reason_codes = ["payment_failed", "potential_balance_deduction"]
        summary = "Customer attempted a payment that failed, with a possible balance deduction."
        reply = _reply(lang, "payments_ops", relevant_txn)

    # --- Refund request ---
    elif any(k in text for k in refund_keywords):
        case_type = "refund_request"
        severity = "low"
        department = "customer_support"
        matches = find_matching_transactions(text, transactions)
        if matches:
            relevant_txn = matches[0]["transaction_id"]
            evidence_verdict = "consistent"
        confidence = 0.85
        human_review_required = False
        reason_codes = ["refund_request", "merchant_policy_dependent"]
        summary = "Customer requests a refund for a completed payment due to change of mind, not a service failure."
        reply = _reply(lang, "refund")

    
    else:
        case_type = "other"
        severity = "low"
        department = "customer_support"
        confidence = 0.5
        human_review_required = False
        reason_codes = ["uncategorized"]
        summary = "Customer reports an issue that requires further investigation."
        reply = _reply(lang, "other")

    return {
        "ticket_id": ticket_id,
        "relevant_transaction_id": relevant_txn,
        "evidence_verdict": evidence_verdict,
        "case_type": case_type,
        "severity": severity,
        "department": department,
        "agent_summary": summary,
        "recommended_next_action": _next_action(case_type, evidence_verdict),
        "customer_reply": reply,
        "human_review_required": human_review_required,
        "confidence": confidence,
        "reason_codes": reason_codes,
    }


def _next_action(case_type: str, evidence_verdict: str) -> str:
    actions = {
        "wrong_transfer": "Verify transaction details with the customer and initiate the wrong-transfer dispute workflow per policy.",
        "payment_failed": "Investigate ledger status. If balance was deducted on a failed payment, initiate the automatic reversal flow within standard SLA.",
        "refund_request": "Inform the customer that refund eligibility depends on the merchant's own policy. Provide guidance on contacting the merchant directly.",
        "duplicate_payment": "Verify the duplicate with payments_ops. If confirmed, initiate reversal of the duplicate transaction.",
        "merchant_settlement_delay": "Route to merchant_operations to verify settlement batch status and communicate a revised ETA.",
        "agent_cash_in_issue": "Investigate the cash-in transaction's pending status with agent operations and resolve within SLA.",
        "phishing_or_social_engineering": "Escalate to fraud_risk team immediately. Confirm to customer that the company never asks for OTP.",
        "other": "Reply to customer asking for specific details: transaction ID, amount, and description of the issue.",
    }
    return actions.get(case_type, actions["other"])


