import os
import pytest
from fastapi.testclient import TestClient
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from backend.app.main import app
from backend.database.database import SessionLocal
from backend.database.models import Email, Prediction, Feedback
import io
from PIL import Image

# Before importing FastAPI app, set DB URL to a test file so connections share it
os.environ["DATABASE_URL"] = "sqlite:///./test_api.db"

client = TestClient(app)

def get_db_counts():
    db = SessionLocal()
    try:
        emails = db.query(Email).count()
        preds = db.query(Prediction).count()
        feedback = db.query(Feedback).count()
        return emails, preds, feedback
    finally:
        db.close()

def test_analyze_manual_ham():
    emails_before, preds_before, fb_before = get_db_counts()
    
    payload = {
        "subject": "Lunch tomorrow?",
        "body": "Hey, are we still meeting for lunch tomorrow at 12?",
        "sender": "colleague@work.com"
    }
    response = client.post("/analyze-manual", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["classification"] == "HAM"
    assert "decision_score" in data
    assert "model_version" in data
    assert data.get("email_id") is None
    
    emails_after, preds_after, fb_after = get_db_counts()
    assert emails_after == emails_before
    assert preds_after == preds_before
    assert fb_after == fb_before

def test_analyze_manual_spam():
    emails_before, preds_before, fb_before = get_db_counts()
    
    payload = {
        "subject": "You Won!",
        "body": "WINNER!! As a valued network customer you have been selected to receive a £900 prize reward! To claim call 09061701461.",
        "sender": "spam@spam.com"
    }
    response = client.post("/analyze-manual", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["classification"] == "SPAM"
    assert "decision_score" in data
    assert "model_version" in data
    assert data.get("email_id") is None
    
    emails_after, preds_after, fb_after = get_db_counts()
    assert emails_after == emails_before
    assert preds_after == preds_before
    assert fb_after == fb_before

def test_predict_remains_unchanged():
    emails_before, preds_before, fb_before = get_db_counts()
    
    payload = {
        "subject": "Meeting",
        "body": "Let's meet tomorrow.",
        "sender": "test@work.com"
    }
    response = client.post("/predict", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data.get("email_id") is not None
    
    emails_after, preds_after, fb_after = get_db_counts()
    assert emails_after == emails_before + 1
    assert preds_after == preds_before + 1
    assert fb_after == fb_before

def test_regression_bug_paste_and_ocr():
    # 1. Count current email records
    emails_before, preds_before, fb_before = get_db_counts()
    
    # 2. Submit pasted manual email
    payload = {
        "subject": "Paste Test",
        "body": "This is a pasted email.",
        "sender": ""
    }
    response = client.post("/analyze-manual", json=payload)
    assert response.status_code == 200
    
    # 3. Count email records again
    emails_after_paste, _, _ = get_db_counts()
    
    # 4. Assert count is unchanged
    assert emails_after_paste == emails_before
    
    # Then:
    # 1. Upload screenshot & 2. Run OCR
    # create a dummy image
    img = Image.new('RGB', (100, 30), color = (255, 255, 255))
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    img_byte_arr = img_byte_arr.getvalue()
    
    # Mock pytesseract for the test
    import pytesseract
    def mock_image_to_string(image, *args, **kwargs):
        return "mock ocr text"
    
    original_ocr = pytesseract.image_to_string
    pytesseract.image_to_string = mock_image_to_string
    
    try:
        files = {"file": ("test.png", img_byte_arr, "image/png")}
        ocr_response = client.post("/ocr", files=files)
        assert ocr_response.status_code == 200
        ocr_text = ocr_response.json().get("text", "")
        assert ocr_text == "mock ocr text"
        
        # 3. Analyze extracted text
        payload_ocr = {
            "subject": "OCR Test",
            "body": ocr_text,
            "sender": ""
        }
        analyze_response = client.post("/analyze-manual", json=payload_ocr)
        assert analyze_response.status_code == 200
        
        # 4. Count email records again
        emails_after_ocr, _, _ = get_db_counts()
        
        # 5. Assert count is unchanged
        assert emails_after_ocr == emails_before
    finally:
        pytesseract.image_to_string = original_ocr
