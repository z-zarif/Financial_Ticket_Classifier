"""Safe reply and recommended-next-action templates per case_type.

All templates are deliberately written to comply with section 8 of the
problem statement:
    * never ask for PIN, OTP, password, or full card number
    * never confirm a refund / reversal / unblock unconditionally
    * never instruct the customer to contact a third party

Placeholder syntax: {ticket_id}, {transaction_id}, {amount}, {counterparty}.
"""

from __future__ import annotations

from typing import TypedDict


class ReplyBundle(TypedDict):
    customer_reply: str
    recommended_next_action: str


_TEMPLATES: dict[str, ReplyBundle] = {
    "wrong_transfer": {
        "customer_reply": (
            "Thank you for reporting ticket {ticket_id}. We have noted your "
            "concern about transaction {transaction_id}. Any eligible amount "
            "may be recoverable through official channels only, subject to "
            "verification by our dispute resolution team. Please do not share "
            "your PIN, OTP, or password with anyone. A support agent will "
            "contact you through the official app or hotline to guide you."
        ),
        "recommended_next_action": (
            "Verify {transaction_id} counterparty and timestamp with the "
            "customer, then open a dispute ticket in the dispute_resolution "
            "queue. Do not confirm recovery; wait for verification."
        ),
    },
    "payment_failed": {
        "customer_reply": (
            "Thank you for reporting ticket {ticket_id}. We have noted your "
            "concern about transaction {transaction_id}. If the transaction "
            "shows a deduction, any eligible amount will be returned through "
            "official channels after our payments operations team completes "
            "their check. Please do not share your PIN, OTP, or password "
            "with anyone."
        ),
        "recommended_next_action": (
            "Pull transaction {transaction_id} from the payments ledger, "
            "confirm whether the deduction is real, and queue for reversal "
            "only after ledger confirmation. Do not confirm reversal to "
            "the customer until approved."
        ),
    },
    "refund_request": {
        "customer_reply": (
            "Thank you for your message on ticket {ticket_id}. We have "
            "recorded your request regarding transaction {transaction_id}. "
            "Any eligible amount will be processed through official "
            "channels after review. Please do not share your PIN, OTP, or "
            "password with anyone, and contact us only through the "
            "official app or hotline."
        ),
        "recommended_next_action": (
            "Review transaction {transaction_id} eligibility for refund per "
            "the platform refund policy. Do not confirm a refund to the "
            "customer; route for approval."
        ),
    },
    "duplicate_payment": {
        "customer_reply": (
            "Thank you for reporting ticket {ticket_id}. We have noted the "
            "possible duplicate charge for transaction {transaction_id}. "
            "Any eligible amount will be returned through official channels "
            "after our payments operations team verifies the duplicate. "
            "Please do not share your PIN, OTP, or password with anyone."
        ),
        "recommended_next_action": (
            "Compare {transaction_id} against recent same-amount entries "
            "for the customer, confirm the duplicate, and queue for "
            "reversal only after ledger confirmation."
        ),
    },
    "merchant_settlement_delay": {
        "customer_reply": (
            "Thank you for reporting ticket {ticket_id}. We have noted your "
            "concern about transaction {transaction_id}. Merchant "
            "settlements are processed through official channels on the "
            "standard schedule, and any eligible amount will be released "
            "after verification by our merchant operations team. Please do "
            "not share your PIN, OTP, or password with anyone."
        ),
        "recommended_next_action": (
            "Check settlement status of {transaction_id} against the "
            "merchant payout queue. Escalate to merchant_operations if "
            "the standard window has passed."
        ),
    },
    "agent_cash_in_issue": {
        "customer_reply": (
            "Thank you for reporting ticket {ticket_id}. We have noted your "
            "concern about transaction {transaction_id}. Any eligible "
            "amount will be reconciled through official channels after our "
            "agent operations team reviews the case. Please do not share "
            "your PIN, OTP, or password with anyone."
        ),
        "recommended_next_action": (
            "Verify {transaction_id} against the agent ledger and the "
            "agent's recent activity. Escalate to agent_operations and "
            "consider agent hold pending review."
        ),
    },
    "phishing_or_social_engineering": {
        "customer_reply": (
            "Thank you for reporting ticket {ticket_id}. We take this very "
            "seriously. Our team will never ask for your PIN, OTP, password, "
            "or full card number. Please do not share those with anyone. "
            "Any eligible reimbursement will only be processed through "
            "official channels after our fraud risk team completes a review. "
            "If you have already shared credentials, please change your "
            "PIN or password now through the official app only."
        ),
        "recommended_next_action": (
            "Escalate {transaction_id} (if any) to fraud_risk queue, lock "
            "the customer account if credentials may be compromised, and "
            "open a fraud case for review. Do not confirm any recovery."
        ),
    },
    "other": {
        "customer_reply": (
            "Thank you for contacting us about ticket {ticket_id}. We have "
            "recorded your message and our support team will follow up "
            "through official channels. Please do not share your PIN, OTP, "
            "or password with anyone."
        ),
        "recommended_next_action": (
            "Route to customer_support for manual triage. Capture any "
            "additional context needed to classify the case further."
        ),
    },
}


def _fallback_bundle() -> ReplyBundle:
    return {
        "customer_reply": (
            "Thank you for contacting us about ticket {ticket_id}. Our "
            "support team will follow up through official channels. "
            "Please do not share your PIN, OTP, or password with anyone."
        ),
        "recommended_next_action": (
            "Route to customer_support for manual triage."
        ),
    }


def get_template(case_type: str) -> ReplyBundle:
    """Return the safe reply + next-action template for a case_type.

    Falls back to the generic "other" template if the case_type is unknown.
    """
    return _TEMPLATES.get(case_type) or _fallback_bundle()


def format_reply(bundle: ReplyBundle, *, ticket_id: str,
                 transaction_id: str | None,
                 counterparty: str | None = None,
                 amount: float | None = None) -> ReplyBundle:
    """Fill placeholders safely. Missing values are substituted with
    non-sensitive defaults so the response is never half-blank.
    """
    safe_txn = transaction_id or "the transaction in question"
    safe_amount = (
        f"{int(amount):,} BDT" if isinstance(amount, (int, float)) and amount else "the amount"
    )
    safe_counterparty = counterparty or "the counterparty"

    def _fill(s: str) -> str:
        return (
            s.replace("{ticket_id}", ticket_id)
            .replace("{transaction_id}", safe_txn)
            .replace("{amount}", safe_amount)
            .replace("{counterparty}", safe_counterparty)
        )

    return {
        "customer_reply": _fill(bundle["customer_reply"]),
        "recommended_next_action": _fill(bundle["recommended_next_action"]),
    }