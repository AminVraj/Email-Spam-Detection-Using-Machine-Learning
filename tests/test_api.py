import os
# Before importing FastAPI app, set DB URL to a test file so connections share it
os.environ["DATABASE_URL"] = "sqlite:///./test_api.db"

import pytest
from fastapi.testclient import TestClient
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.app.main import app
from backend.database.database import init_db

@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    init_db()
    yield
    db_path = "./test_api.db"
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except Exception:
            pass

client = TestClient(app)
client.headers["Authorization"] = "Bearer mock_token_testuser"

def test_health_endpoint():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}

def test_model_info_endpoint():
    response = client.get("/model/info")
    assert response.status_code == 200
    data = response.json()
    assert "version" in data
    assert "algorithm" in data
    assert "evaluation_metrics" in data
    assert "feature_configuration" in data

def test_predict_endpoint_spam():
    payload = {
        "subject": "You Won!",
        "body": "WINNER!! As a valued network customer you have been selected to receivea £900 prize reward! To claim call 09061701461.",
        "sender": "spam@spam.com"
    }
    response = client.post("/predict", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["classification"] == "SPAM"
    assert "decision_score" in data
    assert "model_version" in data
    assert "email_id" in data

def test_predict_endpoint_ham():
    payload = {
        "subject": "Lunch tomorrow?",
        "body": "Hey, are we still meeting for lunch tomorrow at 12?",
        "sender": "colleague@work.com"
    }
    response = client.post("/predict", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["classification"] == "HAM"

def test_predict_endpoint_legitimate_free():
    payload = {
        "subject": "Project update",
        "body": "Feel free to check the new branch when you have time.",
        "sender": "dev@work.com"
    }
    response = client.post("/predict", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["classification"] == "HAM"

def test_predict_endpoint_legitimate_urgent():
    payload = {
        "subject": "Urgent server issue",
        "body": "The production server is down. This is an urgent issue.",
        "sender": "alert@work.com"
    }
    response = client.post("/predict", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["classification"] == "HAM"

def test_predict_endpoint_legitimate_course_material():
    payload = {
        "subject": "Free course material for students",
        "body": "The university provides free course material and urgent updates through the student portal.",
        "sender": "university@edu.com"
    }
    response = client.post("/predict", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "classification" in data

def test_predict_endpoint_unicode():
    payload = {
        "subject": "Hello 🌍",
        "body": "This is an test email containing unicode 漢字.",
        "sender": "international@test.com"
    }
    response = client.post("/predict", json=payload)
    assert response.status_code == 200
    assert response.json()["classification"] in ["HAM", "SPAM"]

def test_predict_endpoint_html():
    payload = {
        "subject": "Newsletter",
        "body": "<html><body><h1>Hello</h1><p>This is a legit email.</p></body></html>",
        "sender": "newsletter@test.com"
    }
    response = client.post("/predict", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "classification" in data
    assert "model_version" in data
    assert "decision_score" in data

def test_predict_endpoint_empty_input():
    payload = {
        "subject": "",
        "body": "",
        "sender": ""
    }
    response = client.post("/predict", json=payload)
    assert response.status_code == 400
    assert "cannot both be empty" in response.json()["detail"]

def test_predict_endpoint_subject_only():
    payload = {
        "subject": "Meeting tomorrow",
        "body": "",
        "sender": "test@example.com"
    }
    response = client.post("/predict", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "classification" in data

def test_predict_endpoint_body_only():
    payload = {
        "subject": "",
        "body": "Hello, this is a legitimate message.",
        "sender": "test@example.com"
    }
    response = client.post("/predict", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "classification" in data

def test_predict_endpoint_very_long_email():
    payload = {
        "subject": "Long",
        "body": "Word " * 25000,
        "sender": "test@test.com"
    }
    response = client.post("/predict", json=payload)
    assert response.status_code == 400
    assert "exceeds maximum allowed length" in response.json()["detail"]

def test_predict_endpoint_malformed_request():
    payload = [{"subject": "Test"}]
    response = client.post("/predict", json=payload)
    assert response.status_code == 422

def test_model_unavailable(monkeypatch):
    from backend.ml.predict import SpamClassifier
    
    def mock_load(self):
        raise FileNotFoundError("Mock model missing")
        
    monkeypatch.setattr(SpamClassifier, "load_model", mock_load)
    
    try:
        from backend.ml.predict import get_classifier, classifier_instance
        import backend.ml.predict as pred_module
        pred_module.classifier_instance = None
        
        response = client.get("/model/info")
        assert response.status_code == 503
            
    finally:
        pred_module.classifier_instance = None

def test_feedback_and_statistics():
    # 1. Predict
    payload = {
        "subject": "Meeting",
        "body": "Let's meet tomorrow.",
        "sender": "test@work.com"
    }
    response = client.post("/predict", json=payload)
    assert response.status_code == 200
    email_id = response.json()["email_id"]
    original_pred = response.json()["classification"]
    
    # 2. Feedback (correction)
    feedback_payload = {
        "email_id": email_id,
        "user_label": "SPAM" if original_pred == "HAM" else "HAM"
    }
    fb_response = client.post("/feedback", json=feedback_payload)
    assert fb_response.status_code == 200
    fb_data = fb_response.json()
    assert fb_data["status"] == "recorded"
    assert fb_data["original_prediction"] == original_pred
    
    # 3. Duplicate feedback (should fail)
    fb_response2 = client.post("/feedback", json=feedback_payload)
    assert fb_response2.status_code == 400
    
    # 4. Invalid feedback label
    fb_response3 = client.post("/feedback", json={"email_id": email_id, "user_label": "UNKNOWN"})
    assert fb_response3.status_code == 400
    
    # 5. Invalid email ID
    fb_response4 = client.post("/feedback", json={"email_id": 999999, "user_label": "HAM"})
    assert fb_response4.status_code == 400
    
    # 6. Check statistics
    stats_response = client.get("/statistics")
    assert stats_response.status_code == 200
    stats = stats_response.json()
    assert stats["total_predictions"] > 0
    assert stats["user_corrections"] > 0
