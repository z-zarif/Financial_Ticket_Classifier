from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from classifier import classify_ticket

app = FastAPI(title="Ticket Sorter API")


class TicketRequest(BaseModel):
    ticket_id: str
    complaint: str
    language: Optional[str] = "en"
    user_type: Optional[str] = "customer"
    transaction_history: Optional[List[Dict[str, Any]]] = []


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }


@app.post("/sort-ticket")
def sort_ticket(ticket: TicketRequest):
    result = classify_ticket(ticket.dict())
    return result