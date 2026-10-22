import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database.models import Base, Email, Prediction
from backend.database.repository import Repository
from fastapi.testclient import TestClient
from backend.app.main import app

from backend.database.database import init_db

# Setup test DB session
TEST_DB_URL = "sqlite:///./test_account_switching.db"
engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="module", autouse=True)
def setup_db():
    init_db()
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    if os.path.exists("./test_account_switching.db"):
        try:
            os.remove("./test_account_switching.db")
        except Exception:
            pass

@pytest.fixture
def db():
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()

client = TestClient(app)
client.headers["Authorization"] = "Bearer mock_token_testuser"

def test_prevent_cross_account_record_collisions(db):
    """
    Tests that identical provider_message_ids from DIFFERENT Gmail accounts (userA@gmail.com vs userB@gmail.com)
    are stored as distinct records without cross-account collisions or accidental record overwriting.
    """
    repo = Repository(db)

    # 1. Record email from userA@gmail.com with provider_message_id "msg_100"
    e1_id, p1_id = repo.record_email_and_prediction(
        subject="Account A Email",
        body="Hello from user A",
        sender="senderA@test.com",
        classification="HAM",
        decision_score=0.1,
        model_version="v1",
        provider="gmail",
        provider_message_id="msg_100",
        account_email="userA@gmail.com"
    )

    # 2. Record email from userB@gmail.com with SAME provider_message_id "msg_100"
    e2_id, p2_id = repo.record_email_and_prediction(
        subject="Account B Email",
        body="Hello from user B",
        sender="senderB@test.com",
        classification="SPAM",
        decision_score=0.9,
        model_version="v1",
        provider="gmail",
        provider_message_id="msg_100",
        account_email="userB@gmail.com"
    )

    # Verify separate IDs were assigned
    assert e1_id != e2_id, "Different Gmail accounts with identical message IDs must produce distinct DB records."

    email_a = db.query(Email).filter(Email.id == e1_id).first()
    email_b = db.query(Email).filter(Email.id == e2_id).first()

    assert email_a.account_email == "userA@gmail.com"
    assert email_b.account_email == "userB@gmail.com"
    assert email_a.subject == "Account A Email"
    assert email_b.subject == "Account B Email"

def test_same_account_deduplication(db):
    """
    Tests that analyzing the SAME email multiple times for the SAME Gmail account returns the existing record.
    """
    repo = Repository(db)

    # First analysis
    e1_id, _ = repo.record_email_and_prediction(
        subject="Dup Test",
        body="Body text",
        sender="sender@test.com",
        classification="HAM",
        decision_score=0.2,
        model_version="v1",
        provider="gmail",
        provider_message_id="msg_200",
        account_email="userA@gmail.com"
    )

    # Second analysis for userA with msg_200
    e2_id, _ = repo.record_email_and_prediction(
        subject="Dup Test",
        body="Body text",
        sender="sender@test.com",
        classification="HAM",
        decision_score=0.2,
        model_version="v1",
        provider="gmail",
        provider_message_id="msg_200",
        account_email="userA@gmail.com"
    )

    assert e1_id == e2_id, "Repeated analysis for same Gmail account and message ID must reuse the existing record."

def test_api_predict_with_account_email():
    """
    Tests /predict endpoint accepts account_email parameter.
    """
    payload = {
        "subject": "API Test",
        "body": "Testing predict endpoint with account email",
        "sender": "sender@test.com",
        "provider": "gmail",
        "provider_message_id": "msg_api_1",
        "account_email": "testuser@gmail.com"
    }

    res = client.post("/predict", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "email_id" in data
    assert data["classification"] in ["HAM", "SPAM"]
