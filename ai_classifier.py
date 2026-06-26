import json
import os
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")

# Define the schema outside the function to keep the core function clean
RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "ticket_id": {"type": "string"},
        "relevant_transaction_id": {"type": "string"},
        "evidence_verdict": {"type": "string"},
        "case_type": {"type": "string"},
        "severity": {"type": "string"},
        "department": {"type": "string"},
        "agent_summary": {"type": "string"},
        "recommended_next_action": {"type": "string"},
        "customer_reply": {"type": "string"},
        "human_review_required": {"type": "boolean"},
        "confidence": {"type": "number"},
        "reason_codes": {
            "type": "array",
            "items": {"type": "string"}
        }
    },
    "required": [
        "ticket_id",
        "relevant_transaction_id",
        "evidence_verdict",
        "case_type",
        "severity",
        "department",
        "agent_summary",
        "recommended_next_action",
        "customer_reply",
        "human_review_required",
        "confidence",
        "reason_codes"
    ]
}

def analyze_dispute_ticket(input_data: dict) -> dict:
    """
    Analyzes a financial services dispute ticket using Gemini 2.5 Flash.
    
    Args:
        input_data (dict): The dynamic ticket details and transaction history.
        api_key (str): Your Gemini API key.
        
    Returns:
        dict: The structured analysis matching the defined response schema.
    """
    # Initialize the client inside the function or pass it as an argument
    client = genai.Client(api_key=api_key)
    
    # Construct the prompt dynamically
    prompt = f"""
You are an AI assistant for a financial services dispute resolution team.

You will receive a JSON object containing:
- A customer complaint.
- Transaction history.
- Customer profile.
- Any supporting evidence.

Your task is to analyze the information and determine the most appropriate case outcome.

For every request:

1. Identify the transaction most relevant to the complaint.
2. Determine whether the evidence is:
   - consistent
   - inconsistent
   - insufficient_evidence
3. Classify the case type.
FYI - THESE ARE THE POSSIBLE CASE TYPES: 
wrong_transfer
payment_failed 
refund_request 
duplicate_payment 
merchant_settlement_delay 
agent_cash_in_issue
4. Assign a severity:
   - low
   - medium
   - high
5. Determine which department should handle the case.
FYI: THESE ARE OUR DEPARTMENTS STRICTLY
customer_support
dispute_resolution
payments_ops
merchant_operations
agent_operations
agent_operations
fraud_risk

The relationship between departments and typical case types are as following:

customer_support for other, low severity refund_request, vague or insufficient data cases.
dispute_resolution for wrong_transfer, contested refund_request.
payments_ops for payment_failed, duplicate_payment.
merchant_operations for merchant_settlement_delay, merchant side complaints.
agent_operations for agent_cash_in_issue, agent side complaints.
fraud_risk for phishing_or_social_engineering, suspicious activity patterns.

6. Generate a concise internal summary for the support agent.
7. Recommend the next action for the support team.
8. Draft a professional response to the customer.
9. Decide whether human review is required.
10. Provide a confidence score between 0.0 and 1.0.
11. Provide one or more reason codes explaining the decision.

Rules:
- Base every decision only on the supplied JSON.
- Do not invent transactions or customer information.
- If evidence is missing, indicate that instead of guessing.
- Confidence should reflect certainty in the available evidence.
- The customer reply should be polite, professional, and avoid making promises that cannot be verified.

Input JSON:

{json.dumps(input_data, indent=2)}
"""

    # Generate content using Structured Outputs
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=RESPONSE_SCHEMA,
            temperature=0.2
        ),
    )

    # Convert the structured JSON string response back to a Python dictionary
    return json.loads(response.text)