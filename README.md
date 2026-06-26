# Financial_Ticket_Classifier
Ticket Sorter API
An automated financial services dispute resolution and ticket classification API powered by FastAPI and the Gemini 2.5 Flash model using the structured outputs feature.

This service dynamically ingests customer complaints and transaction histories, cross-analyzes them for consistency, routes them to the correct department, determines risk severity, and drafts an immediate, contextual response for the user.

Tech Stack
Framework: FastAPI (Python 3.10+)

LLM SDK: google-genai (Gemini 2.5 Flash)

Data Validation: Pydantic v2

Environment Management: python-dotenv

Getting Started
1. Clone & Navigate
Bash
git clone <your-repository-url>
cd ticket-sorter-api
2. Set Up a Virtual Environment
Bash
# Create environment
python -m venv venv

# Activate environment (Windows)
.\venv\Scripts\activate

# Activate environment (Mac/Linux)
source venv/bin/activate
3. Install Dependencies
Bash
pip install fastapi uvicorn google-genai python-dotenv pydantic
4. Configure Environment Variables
Create a .env file in the root directory of your project and populate it with your Gemini API credentials:

Code snippet
GEMINI_API_KEY=your_actual_gemini_api_key_here
Running the Server Locally
Start the local development server using uvicorn:

Bash
uvicorn app:app --reload
The API will be hosted locally at http://127.0.0.1:8000.

API Endpoints
1. Health Check
Endpoint: GET /health

Description: Verifies that the server is operational.

Response:

JSON
{ "status": "healthy" }
2. Sort & Analyze Ticket
Endpoint: POST /sort-ticket

Description: Accepts a structured payload representing a customer's complaint and transaction history, evaluating the data against the language model's reasoning layers.

Expected Request Payload (POST)
JSON
{
  "ticket_id": "TKT-001",
  "complaint": "I sent 5000 taka to a wrong number around 2pm today...",
  "language": "en",
  "channel": "in_app_chat",
  "user_type": "customer",
  "campaign_context": "boishakh_bonanza_day_1",
  "transaction_history": [
    {
      "transaction_id": "TXN-9101",
      "timestamp": "2026-04-14T14:08:22Z",
      "type": "transfer",
      "amount": 5000,
      "counterparty": "+8801719876543",
      "status": "completed"
    }
  ]
}
Structured JSON Output Response
The output is constrained by a defined target schema, ensuring the model response adheres to the following format:

JSON
{
  "ticket_id": "TKT-001",
  "relevant_transaction_id": "TXN-9101",
  "evidence_verdict": "consistent",
  "case_type": "wrong_number_transfer",
  "severity": "medium",
  "department": "accounts_and_settlements",
  "agent_summary": "Customer mistakenly sent 5,000 BDT to an incorrect wallet address. The transaction log confirms a completed transfer matching the timeframe.",
  "recommended_next_action": "Freeze funds provisionally in the destination account if internal policy permits, and reach out to the counterparty recipient.",
  "customer_reply": "Dear customer, we have received your request regarding the accidental transfer. We have successfully logged transaction TXN-9101 for routing review. Our specialized team is investigating...",
  "human_review_required": true,
  "confidence": 0.95,
  "reason_codes": [
    "MATCHING_TXN_FOUND",
    "CROSS_ACCOUNT_TRANSFER"
  ]
}
Project Structure
Plaintext
├── app.py                # FastAPI endpoints & Pydantic request models
├── ai_classifier.py     # Gemini client initialization, structured schema & core logic
├── .env                  # Environment secrets (ignored by git)
└── README.md             # Project documentation
Interface Testing
When the server is active, navigate to http://127.0.0.1:8000/docs to access the interactive Swagger UI. This interface allows for real-time testing of payloads directly against the endpoint.