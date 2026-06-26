from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from ai_classifier import analyze_dispute_ticket
from classifier import classify_ticket

app = FastAPI(title="Ticket Sorter API")

# Define nested schemas so FastAPI knows exactly what to expect
class Transaction(BaseModel):
    transaction_id: str
    timestamp: str
    type: str
    amount: float
    counterparty: str
    status: str

class TicketRequest(BaseModel):
    ticket_id: str
    complaint: str
    language: Optional[str] = "en"
    channel: Optional[str] = None
    user_type: Optional[str] = None
    campaign_context: Optional[str] = None
    transaction_history: List[Transaction] = []

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/sort-ticket")
def sort_ticket(ticket: TicketRequest):
    try:
        # Convert the Pydantic object into a native Python dictionary
        ticket_dict = ticket.model_dump()
        
        # Pass the full dictionary to the classifier
        result = analyze_dispute_ticket(ticket_dict)
        
        return result
    except Exception as e:
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail=str(e))