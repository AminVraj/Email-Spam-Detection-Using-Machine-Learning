import os
import sys
import pytest
from fastapi.testclient import TestClient

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.app.main import app
from backend.database.database import init_db
from backend.database.repository import Repository
from backend.database.models import Email, Prediction

@pytest.fixture(scope="module", autouse=True)
def setup_promo_db():
    init_db()
    yield

client = TestClient(app)
client.headers["Authorization"] = "Bearer mock_token_promotester"

def test_category_mapping_promotions_spam():
    """Verify promotional email with an underlying SPAM prediction."""
    payload = {
        "subject": "Exclusive Discount 90% OFF! Claim now!",
        "body": "WINNER!! Claim your £900 prize reward call 09061701461 now!",
        "sender": "offers@promo.com",
        "provider": "gmail",
        "provider_message_id": "promo_msg_spam_1",
        "provider_category": "PROMOTIONS"
    }

    res = client.post("/predict", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["classification"] == "SPAM"
    email_id = data["email_id"]

    # Verify retrieval via /emails/{id}
    detail_res = client.get(f"/emails/{email_id}")
    assert detail_res.status_code == 200
    detail = detail_res.json()
    # Display classification is PROMOTION, underlying ML is SPAM
    assert detail["classification"] == "PROMOTION"
    assert detail["provider_category"] == "PROMOTIONS"
    assert detail["ml_prediction"] == "SPAM"

def test_category_mapping_promotions_ham():
    """Verify promotional email with an underlying HAM prediction."""
    payload = {
        "subject": "Weekly Newsletter: AI Engineering Highlights",
        "body": "Here are this week's curated articles on deep learning and software architecture.",
        "sender": "newsletter@techinsights.com",
        "provider": "gmail",
        "provider_message_id": "promo_msg_ham_1",
        "provider_category": "PROMOTIONS"
    }

    res = client.post("/predict", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["classification"] == "HAM"
    email_id = data["email_id"]

    detail_res = client.get(f"/emails/{email_id}")
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert detail["classification"] == "PROMOTION"
    assert detail["provider_category"] == "PROMOTIONS"
    assert detail["ml_prediction"] == "HAM"

def test_category_mapping_primary_email():
    """Verify primary email preserves ML prediction as classification."""
    payload = {
        "subject": "Project sync meeting notes",
        "body": "Hey team, attached are the action items from our morning architecture review.",
        "sender": "lead@company.com",
        "provider": "gmail",
        "provider_message_id": "primary_msg_1",
        "provider_category": "PRIMARY"
    }

    res = client.post("/predict", json=payload)
    assert res.status_code == 200
    data = res.json()
    email_id = data["email_id"]

    detail_res = client.get(f"/emails/{email_id}")
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert detail["classification"] == "HAM"
    assert detail["provider_category"] == "PRIMARY"
    assert detail["ml_prediction"] == "HAM"

def test_category_mapping_social_updates_forums():
    """Verify SOCIAL, UPDATES, and FORUMS categories retain their provider category and ML classification."""
    for cat in ["SOCIAL", "UPDATES", "FORUMS"]:
        payload = {
            "subject": f"Notification from {cat}",
            "body": f"Someone mentioned you in {cat} forum discussion.",
            "sender": f"notifications@{cat.lower()}.com",
            "provider": "gmail",
            "provider_message_id": f"msg_{cat.lower()}_1",
            "provider_category": cat
        }
        res = client.post("/predict", json=payload)
        assert res.status_code == 200
        email_id = res.json()["email_id"]

        detail = client.get(f"/emails/{email_id}").json()
        assert detail["provider_category"] == cat
        # When not PROMOTIONS, classification equals ML prediction
        assert detail["classification"] == detail["ml_prediction"]

def test_category_normalization_invalid_category_defaults_primary():
    """Verify arbitrary or unknown category values are sanitized to PRIMARY."""
    payload = {
        "subject": "Testing unknown category sanitization",
        "body": "Checking category normalization on backend.",
        "sender": "test@domain.com",
        "provider": "gmail",
        "provider_message_id": "msg_unknown_cat_1",
        "provider_category": "UNKNOWN_CUSTOM_HACK"
    }
    res = client.post("/predict", json=payload)
    assert res.status_code == 200
    email_id = res.json()["email_id"]

    detail = client.get(f"/emails/{email_id}").json()
    assert detail["provider_category"] == "PRIMARY"

def test_dashboard_statistics_separate_promotion_count():
    """Verify promotions are counted separately in statistics without being double-counted in spam/ham."""
    stats = client.get("/statistics").json()
    assert "promotions_count" in stats
    assert stats["promotions_count"] >= 2
    # Verify total_predictions encompasses promotions without double counting
    assert stats["total_predictions"] >= stats["spam_predictions"] + stats["ham_predictions"] + stats["promotions_count"]

def test_inbox_filtering_serialization():
    """Verify /emails endpoint serializes provider_category and classification correctly for inbox UI."""
    emails = client.get("/emails?limit=100").json()["emails"]
    promotions = [e for e in emails if e["classification"] == "PROMOTION"]
    assert len(promotions) >= 2
    for p in promotions:
        assert p["provider_category"] == "PROMOTIONS"
        assert p["ml_prediction"] in ["SPAM", "HAM"]
