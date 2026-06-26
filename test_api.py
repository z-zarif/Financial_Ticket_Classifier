from fastapi.testclient import TestClient
from app import app

client = TestClient(app)


def test_wrong_transfer():
    response = client.post(
        "/sort-ticket",
        json={
            "ticket_id": "T-001",
            "message": "I sent 3000 to wrong number"
        }
    )

    data = response.json()

    assert response.status_code == 200
    assert data["case_type"] == "wrong_transfer"
    assert data["severity"] == "high"


def test_payment_failed():
    response = client.post(
        "/sort-ticket",
        json={
            "ticket_id": "T-002",
            "message": "Payment failed but balance deducted"
        }
    )

    data = response.json()

    assert response.status_code == 200
    assert data["case_type"] == "payment_failed"
    assert data["severity"] == "high"


def test_phishing():
    response = client.post(
        "/sort-ticket",
        json={
            "ticket_id": "T-003",
            "message": "Someone called asking my OTP, is that bKash?"
        }
    )

    data = response.json()

    assert response.status_code == 200
    assert data["case_type"] == "phishing_or_social_engineering"
    assert data["severity"] == "critical"
    assert data["human_review_required"] is True


def test_refund_request():
    response = client.post(
        "/sort-ticket",
        json={
            "ticket_id": "T-004",
            "message": "Please refund my last transaction, I changed my mind"
        }
    )

    data = response.json()

    assert response.status_code == 200
    assert data["case_type"] == "refund_request"
    assert data["severity"] == "low"


def test_other():
    response = client.post(
        "/sort-ticket",
        json={
            "ticket_id": "T-005",
            "message": "App crashed when I opened it"
        }
    )

    data = response.json()

    assert response.status_code == 200
    assert data["case_type"] == "other"
    assert data["severity"] == "low"