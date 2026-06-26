# Financial_Ticket_Classifier
Ticket Sorter API
An automated financial services dispute resolution and ticket classification API powered by FastAPI and the Gemini 2.5 Flash model using the structured outputs feature.

This service dynamically ingests customer complaints and transaction histories, cross-analyzes them for consistency, routes them to the correct department, determines risk severity, and drafts an immediate, contextual response for the user.

Live URL: https://financial-ticket-classifier.onrender.com/

Tech Stack
Framework: FastAPI (Python 3.10+)

LLM SDK: google-genai (Gemini 2.5 Flash)

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
{ "status": "ok" }
2. Sort & Analyze Ticket
Endpoint: POST /sort-ticket

Description: Accepts a structured payload representing a customer's complaint and transaction history, evaluating the data against the language model's reasoning layers.testing of payloads directly against the endpoint.
