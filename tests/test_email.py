import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime
import os

from backend.email.models import EmailMessage, AttachmentMetadata
from backend.email.base import EmailProvider
from backend.email.gmail import GmailProvider
from backend.email.service import EmailSyncService

# Setup fake DB for tests
from backend.database.models import Base
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def test_normalized_email_message():
    msg = EmailMessage(
        id="123",
        provider="test",
        sender="test@test.com",
        recipients=["to@test.com"],
        subject="Test",
        body="Body",
        received_at=datetime.utcnow(),
        headers={"From": "test@test.com"},
        attachments=[AttachmentMetadata("file.txt", "text/plain", 100)]
    )
    assert msg.id == "123"
    assert msg.attachments[0].filename == "file.txt"

def test_provider_abstraction():
    class DummyProvider(EmailProvider):
        def authenticate(self): return True
        def fetch_emails(self, limit=20): return []
        def get_email(self, msg_id): return None

    p = DummyProvider()
    assert p.authenticate() is True
    assert p.fetch_emails() == []

@patch("backend.email.gmail.IMAPClient")
def test_gmail_provider_auth(mock_imap):
    with patch.dict(os.environ, {"GMAIL_EMAIL": "test@gmail.com", "GMAIL_APP_PASSWORD": "pass"}):
        provider = GmailProvider()
        mock_instance = mock_imap.return_value
        assert provider.authenticate() is True
        mock_instance.login.assert_called_with("test@gmail.com", "pass")

@patch("backend.email.gmail.IMAPClient")
def test_gmail_provider_auth_failure(mock_imap):
    with patch.dict(os.environ, {}, clear=True):
        provider = GmailProvider()
        assert provider.authenticate() is False

def create_mock_raw_email(content_type="text/plain", body="Hello", subject="Test Subject"):
    import email.message
    msg = email.message.EmailMessage()
    if "html" in content_type:
        msg.set_content(body, subtype="html")
    else:
        msg.set_content(body)
    msg["Subject"] = subject
    msg["From"] = "sender@test.com"
    msg["To"] = "receiver@test.com"
    msg["Message-ID"] = "<test-123>"
    return msg.as_bytes()

def test_gmail_parsing_plain_text():
    provider = GmailProvider()
    raw = create_mock_raw_email(content_type="text/plain", body="Plain text body")
    parsed = provider._parse_message(1, raw)
    assert parsed.subject == "Test Subject"
    assert "Plain text body" in parsed.body
    assert parsed.sender == "sender@test.com"
    assert parsed.id == "<test-123>"

def test_gmail_parsing_html_fallback():
    provider = GmailProvider()
    raw = create_mock_raw_email(content_type="text/html", body="<html><body>HTML body</body></html>")
    parsed = provider._parse_message(1, raw)
    assert "HTML body" in parsed.body

def test_gmail_parsing_missing_subject_body():
    provider = GmailProvider()
    import email.message
    msg = email.message.EmailMessage()
    msg.set_content("")
    del msg["Subject"]
    parsed = provider._parse_message(1, msg.as_bytes())
    assert parsed.subject == ""
    assert parsed.body.strip() == ""

def test_gmail_parsing_attachments():
    provider = GmailProvider()
    import email.message
    msg = email.message.EmailMessage()
    msg["Subject"] = "With Attachment"
    msg["Message-ID"] = "<att-123>"
    msg.set_content("Body")
    msg.add_attachment(b"dummy data", maintype="application", subtype="pdf", filename="test.pdf")

    parsed = provider._parse_message(1, msg.as_bytes())
    assert len(parsed.attachments) == 1
    assert parsed.attachments[0].filename == "test.pdf"
    assert parsed.attachments[0].size == len(b"dummy data")

@patch("backend.email.gmail.GmailProvider.authenticate", return_value=True)
@patch("backend.email.gmail.GmailProvider.fetch_emails")
def test_email_sync_service(mock_fetch, mock_auth, db_session):
    mock_fetch.return_value = [
        EmailMessage(
            id="msg1", provider="gmail", sender="spammer@spam.com", recipients=[],
            subject="WINNER!!", body="You won a prize! Call now.", headers={}
        ),
        EmailMessage(
            id="msg2", provider="gmail", sender="friend@test.com", recipients=[],
            subject="Lunch", body="Are we still meeting?", headers={}
        ),
        EmailMessage( # duplicate
            id="msg2", provider="gmail", sender="friend@test.com", recipients=[],
            subject="Lunch", body="Are we still meeting?", headers={}
        ),
        EmailMessage( # empty
            id="msg4", provider="gmail", sender="test@test.com", recipients=[],
            subject="", body="", headers={}
        )
    ]

    service = EmailSyncService(db_session)
    summary = service.sync_recent(limit=4)

    assert summary["fetched"] == 4
    assert summary["skipped_existing"] == 1 # msg2 duplicate
    assert summary["skipped_invalid"] == 1 # empty msg4
    assert summary["processed"] == 2 # msg1 and msg2(first)
    assert summary["spam"] == 1 # msg1
    assert summary["ham"] == 1 # msg2

@patch("backend.email.gmail.GmailProvider.authenticate", return_value=True)
@patch("backend.email.gmail.GmailProvider.fetch_emails")
def test_email_sync_service_promotions(mock_fetch, mock_auth, db_session):
    mock_fetch.return_value = [
        EmailMessage(
            id="promo1", provider="gmail", provider_category="PROMOTIONS", sender="marketing@promo.com", recipients=[],
            subject="50% OFF", body="Buy now!", headers={}
        ),
        EmailMessage(
            id="promo2_spam", provider="gmail", provider_category="PROMOTIONS", sender="spammer@spam.com", recipients=[],
            subject="WINNER!!", body="You won a prize! Call now.", headers={}
        ),
        EmailMessage(
            id="primary1", provider="gmail", provider_category="PRIMARY", sender="friend@test.com", recipients=[],
            subject="Lunch", body="Are we still meeting?", headers={}
        )
    ]

    service = EmailSyncService(db_session)
    summary = service.sync_recent(limit=3)

    # promo1 is promotions+ham -> PROMOTION.
    # promo2_spam is promotions+spam -> PROMOTIONS (or SPAM depending on how mapped, but count as fetched)
    # primary1 is primary+ham -> HAM
    assert summary["fetched"] == 3
    assert summary["promotions"] >= 1


def test_auth_status_endpoint():
    from fastapi.testclient import TestClient
    from backend.app.main import app
    client = TestClient(app)
    client.headers["Authorization"] = "Bearer mock_token_admin"

    with patch("backend.email.gmail.GmailProvider.authenticate", return_value=True):
        response = client.get("/gmail/auth/status")
        assert response.status_code == 200
        assert response.json()["authenticated"] is True

def test_sync_endpoint():
    from fastapi.testclient import TestClient
    from backend.app.main import app
    client = TestClient(app)
    client.headers["Authorization"] = "Bearer mock_token_admin"

    with patch("backend.email.service.EmailSyncService.sync_recent", return_value={"fetched": 1, "processed": 1}):
        response = client.post("/gmail/sync")
        assert response.status_code == 200
        assert response.json()["fetched"] == 1

# --- NORMALIZER UNIT TESTS ---
from backend.email.normalizer import normalize_email_body

def test_normalize_plain_text():
    raw = "Hello, this is a normal email."
    assert normalize_email_body(raw) == "Hello, this is a normal email."

def test_normalize_html_entities():
    raw = "Hello &amp; welcome"
    assert normalize_email_body(raw) == "Hello & welcome"

def test_normalize_non_breaking_space():
    raw = "Hello&nbsp;World"
    assert normalize_email_body(raw) == "Hello World"

def test_normalize_soft_hyphen():
    raw = "Hello&shy;World"
    cleaned = normalize_email_body(raw)
    assert "&shy;" not in cleaned
    assert "\u00ad" not in cleaned
    assert "HelloWorld" in cleaned

def test_normalize_html_tags():
    raw = "<p>Hello</p><p>World</p>"
    cleaned = normalize_email_body(raw, is_html=True)
    assert "Hello" in cleaned
    assert "World" in cleaned
    assert "<p>" not in cleaned

def test_normalize_script_removal():
    raw = "<script>alert('xss')</script><p>Clean content</p>"
    cleaned = normalize_email_body(raw, is_html=True)
    assert "alert" not in cleaned
    assert "Clean content" in cleaned

def test_normalize_html_only_email():
    raw = "<html><body><h1>Special Offer</h1><p>Click &amp; win &shy; today!</p></body></html>"
    cleaned = normalize_email_body(raw, is_html=True)
    assert "Special Offer" in cleaned
    assert "Click & win  today!" in cleaned or "Click & win today!" in cleaned
    assert "&shy;" not in cleaned

def test_gmail_parsing_multipart_prefer_plain_text():
    import email.message
    msg = email.message.EmailMessage()
    msg["Subject"] = "Multipart Test"
    msg["From"] = "sender@test.com"
    msg["To"] = "receiver@test.com"
    msg["Message-ID"] = "<multi-123>"
    msg.set_content("Plain text version &amp; content")
    msg.add_alternative("<p>HTML version &amp; content</p>", subtype="html")

    provider = GmailProvider()
    parsed = provider._parse_message(1, msg.as_bytes())
    assert "Plain text version & content" in parsed.body


