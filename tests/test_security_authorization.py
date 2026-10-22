import os
import sys
import pytest
from fastapi.testclient import TestClient

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.app.main import app
from backend.database.database import init_db

@pytest.fixture(scope="module", autouse=True)
def setup_security_db():
    init_db()
    yield

client = TestClient(app)

def test_unauthenticated_requests_return_401():
    """Verify that unauthenticated requests to protected endpoints return HTTP 401."""
    # 1. /predict
    res = client.post("/predict", json={"subject": "Hi", "body": "Hello world"})
    assert res.status_code == 401
    assert "Authentication required" in res.json()["detail"]

    # 2. /emails
    res = client.get("/emails")
    assert res.status_code == 401

    # 3. /emails/1
    res = client.get("/emails/1")
    assert res.status_code == 401

    # 4. /feedback
    res = client.post("/feedback", json={"email_id": 1, "user_label": "SPAM"})
    assert res.status_code == 401

    # 5. /statistics
    res = client.get("/statistics")
    assert res.status_code == 401

    # 6. /feedback/quality-report
    res = client.get("/feedback/quality-report")
    assert res.status_code == 401

    # 7. /models
    res = client.get("/models")
    assert res.status_code == 401

    # 8. /models/train-candidate
    res = client.post("/models/train-candidate", json={})
    assert res.status_code == 401

    # 9. /models/v2/promote
    res = client.post("/models/v2/promote")
    assert res.status_code == 401

    # 10. /models/v1/rollback
    res = client.post("/models/v1/rollback")
    assert res.status_code == 401

    # 11. /gmail/sync
    res = client.post("/gmail/sync")
    assert res.status_code == 401

    # 12. /gmail/auth/status
    res = client.get("/gmail/auth/status")
    assert res.status_code == 401

def test_invalid_and_expired_tokens_return_401():
    """Verify that invalid, expired, and wrong audience tokens return HTTP 401."""
    # Invalid token
    res = client.get("/emails", headers={"Authorization": "Bearer mock_token_invalid"})
    assert res.status_code == 401
    assert "Invalid" in res.json()["detail"]

    # Expired token
    res = client.get("/emails", headers={"Authorization": "Bearer mock_token_expired"})
    assert res.status_code == 401
    assert "expired" in res.json()["detail"].lower()

    # Wrong audience token
    res = client.get("/emails", headers={"Authorization": "Bearer mock_token_wrong_aud"})
    assert res.status_code == 401
    assert "audience" in res.json()["detail"].lower()

def test_session_cookie_authentication_flow():
    """Verify creating a session from token, using session cookie, and logging out."""
    # 1. Exchange token for session cookie
    res = client.post("/auth/session", json={"token": "mock_token_user1"})
    assert res.status_code == 200
    assert res.json()["status"] == "authenticated"
    assert res.json()["email"] == "user1@gmail.com"
    assert "sentinel_session" in res.cookies

    session_cookie = res.cookies["sentinel_session"]

    # 2. Access /auth/me with session cookie
    me_res = client.get("/auth/me", cookies={"sentinel_session": session_cookie})
    assert me_res.status_code == 200
    assert me_res.json()["email"] == "user1@gmail.com"
    assert me_res.json()["auth_method"] == "session"

    # 3. Access protected /emails with session cookie
    emails_res = client.get("/emails", cookies={"sentinel_session": session_cookie})
    assert emails_res.status_code == 200

    # 4. Logout
    logout_res = client.post("/auth/logout")
    assert logout_res.status_code == 200
    # Cookie should be deleted/cleared
    assert logout_res.cookies.get("sentinel_session") == "" or "sentinel_session" not in logout_res.cookies

def test_account_isolation_emails_and_details():
    """Verify User A cannot view User B's emails or email details."""
    headers_a = {"Authorization": "Bearer mock_token_alice"}
    headers_b = {"Authorization": "Bearer mock_token_bob"}

    # 1. Alice records an email
    res_a = client.post("/predict", headers=headers_a, json={
        "subject": "Alice Private Note",
        "body": "Secret plans for Alice only.",
        "sender": "alice@corp.com"
    })
    assert res_a.status_code == 200
    alice_email_id = res_a.json()["email_id"]

    # 2. Bob records an email
    res_b = client.post("/predict", headers=headers_b, json={
        "subject": "Bob Public Note",
        "body": "Notice board for Bob.",
        "sender": "bob@corp.com"
    })
    assert res_b.status_code == 200
    bob_email_id = res_b.json()["email_id"]

    # 3. Alice lists emails -> contains Alice's email, does NOT contain Bob's email
    alice_list = client.get("/emails", headers=headers_a).json()["emails"]
    alice_ids = [e["id"] for e in alice_list]
    assert alice_email_id in alice_ids
    assert bob_email_id not in alice_ids

    # 4. Bob lists emails -> contains Bob's email, does NOT contain Alice's email
    bob_list = client.get("/emails", headers=headers_b).json()["emails"]
    bob_ids = [e["id"] for e in bob_list]
    assert bob_email_id in bob_ids
    assert alice_email_id not in bob_ids

    # 5. Alice accesses her own email details -> 200 OK
    alice_details = client.get(f"/emails/{alice_email_id}", headers=headers_a)
    assert alice_details.status_code == 200
    assert alice_details.json()["subject"] == "Alice Private Note"

    # 6. Bob attempts to access Alice's email details -> 403 Forbidden!
    bob_attempt = client.get(f"/emails/{alice_email_id}", headers=headers_b)
    assert bob_attempt.status_code == 403
    assert "belongs to another account" in bob_attempt.json()["detail"].lower()

def test_cross_account_feedback_submission_rejected():
    """Verify that User B cannot submit feedback for User A's email."""
    headers_a = {"Authorization": "Bearer mock_token_user_alpha"}
    headers_b = {"Authorization": "Bearer mock_token_user_beta"}

    # Alpha creates email
    res_alpha = client.post("/predict", headers=headers_a, json={
        "subject": "Alpha Urgent Notice",
        "body": "Urgent update on system architecture.",
        "sender": "alert@tech.com"
    })
    assert res_alpha.status_code == 200
    alpha_email_id = res_alpha.json()["email_id"]

    # Beta attempts to submit feedback on Alpha's email -> 403 Forbidden
    beta_fb = client.post("/feedback", headers=headers_b, json={
        "email_id": alpha_email_id,
        "user_label": "SPAM"
    })
    assert beta_fb.status_code == 403
    assert "another user account" in beta_fb.json()["detail"].lower()

    # Alpha submits feedback on Alpha's email -> 200 OK
    alpha_fb = client.post("/feedback", headers=headers_a, json={
        "email_id": alpha_email_id,
        "user_label": "HAM"
    })
    assert alpha_fb.status_code == 200
    assert alpha_fb.json()["status"] == "recorded"

def test_account_scoped_statistics():
    """Verify that statistics endpoint returns metrics scoped to the authenticated user."""
    headers_u1 = {"Authorization": "Bearer mock_token_statsuser1"}
    headers_u2 = {"Authorization": "Bearer mock_token_statsuser2"}

    # StatsUser1 creates 2 emails
    client.post("/predict", headers=headers_u1, json={"subject": "Email 1", "body": "Free bonus money now!"})
    client.post("/predict", headers=headers_u1, json={"subject": "Email 2", "body": "Hey, how are you doing today?"})

    # StatsUser2 creates 1 email
    client.post("/predict", headers=headers_u2, json={"subject": "Email 3", "body": "Meeting at 3pm."})

    stats_u1 = client.get("/statistics", headers=headers_u1).json()
    stats_u2 = client.get("/statistics", headers=headers_u2).json()

    assert stats_u1["total_predictions"] >= 2
    assert stats_u2["total_predictions"] >= 1
    # User 2 has fewer predictions than User 1
    assert stats_u2["total_predictions"] < stats_u1["total_predictions"]

def test_account_mismatch_in_predict_rejected():
    """Verify that submitting an account_email that does not match authenticated token is rejected with 403."""
    headers_alice = {"Authorization": "Bearer mock_token_alice"}

    # Alice passes Bob's email in request body
    res = client.post("/predict", headers=headers_alice, json={
        "subject": "Spoof attempt",
        "body": "Trying to impersonate Bob",
        "account_email": "bob@gmail.com"
    })
    assert res.status_code == 403
    assert "account mismatch" in res.json()["detail"].lower()

def test_unauthorized_model_management_rejected():
    """Verify standard users cannot train, promote, or rollback models, while admins can."""
    headers_user = {"Authorization": "Bearer mock_token_regularuser"}
    headers_admin = {"Authorization": "Bearer mock_token_admin"}

    # 1. Candidate training
    res_user_train = client.post("/models/train-candidate", headers=headers_user, json={})
    assert res_user_train.status_code == 403
    assert "Administrative privileges required" in res_user_train.json()["detail"]

    # 2. Model promotion
    res_user_promote = client.post("/models/v2/promote", headers=headers_user)
    assert res_user_promote.status_code == 403
    assert "Administrative privileges required" in res_user_promote.json()["detail"]

    # 3. Model rollback
    res_user_rollback = client.post("/models/v1/rollback", headers=headers_user)
    assert res_user_rollback.status_code == 403
    assert "Administrative privileges required" in res_user_rollback.json()["detail"]

    # 4. IMAP sync
    res_user_sync = client.post("/gmail/sync", headers=headers_user)
    assert res_user_sync.status_code == 403
    assert "Administrative privileges required" in res_user_sync.json()["detail"]

    # 5. Admin can access IMAP auth status
    res_admin_status = client.get("/gmail/auth/status", headers=headers_admin)
    assert res_admin_status.status_code == 200
    assert "authenticated" in res_admin_status.json()

def test_cors_origin_policy():
    """Verify that configured origins and Chrome extension origins are permitted, and unknown origins are not."""
    # 1. Allowed frontend origin
    res_allowed = client.options("/health", headers={
        "Origin": "http://localhost:5173",
        "Access-Control-Request-Method": "GET"
    })
    assert res_allowed.headers.get("access-control-allow-origin") == "http://localhost:5173"

    # 2. Allowed Chrome extension origin
    res_ext = client.options("/health", headers={
        "Origin": "chrome-extension://abcdefghijklmnop",
        "Access-Control-Request-Method": "GET"
    })
    assert res_ext.headers.get("access-control-allow-origin") == "chrome-extension://abcdefghijklmnop"

    # 3. Disallowed origin
    res_disallowed = client.options("/health", headers={
        "Origin": "https://malicious-site.com",
        "Access-Control-Request-Method": "GET"
    })
    assert res_disallowed.headers.get("access-control-allow-origin") is None
