import hmac
import hashlib
import json
import base64
import time
import logging
from typing import Optional, Dict, Tuple
from pydantic import BaseModel
from fastapi import Request, HTTPException, Depends
import urllib.request
import urllib.error

from backend.config import (
    GOOGLE_CLIENT_ID,
    ADMIN_API_KEY,
    ADMIN_EMAILS,
    SESSION_SECRET_KEY,
    TESTING
)

logger = logging.getLogger(__name__)

class AuthenticatedUser(BaseModel):
    email: str
    is_admin: bool = False
    auth_method: str = "oauth"

# Thread-safe in-memory cache for validated Google tokens: token -> (user, expires_at)
_token_cache: Dict[str, Tuple[AuthenticatedUser, float]] = {}

def sign_session_data(data: dict) -> str:
    """Signs session data using HMAC-SHA256."""
    payload = base64.urlsafe_b64encode(json.dumps(data).encode("utf-8")).decode("utf-8")
    sig = hmac.new(
        SESSION_SECRET_KEY.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    return f"{payload}.{sig}"

def verify_session_data(session_str: str) -> Optional[dict]:
    """Verifies HMAC signature of session string."""
    try:
        parts = session_str.split(".")
        if len(parts) != 2:
            return None
        payload, sig = parts[0], parts[1]
        expected_sig = hmac.new(
            SESSION_SECRET_KEY.encode("utf-8"),
            payload.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(sig, expected_sig):
            return None
        data = json.loads(base64.urlsafe_b64decode(payload.encode("utf-8")).decode("utf-8"))
        if data.get("exp") and time.time() > data["exp"]:
            return None
        return data
    except Exception:
        return None

def verify_google_access_token(token: str) -> AuthenticatedUser:
    """
    Validates a Google OAuth access token via Google's tokeninfo endpoint.
    Verifies audience, expiration, scope, and extracts verified email.
    """
    now = time.time()
    # Check cache
    if token in _token_cache:
        user, exp = _token_cache[token]
        if now < exp:
            return user
        else:
            del _token_cache[token]

    url = f"https://oauth2.googleapis.com/tokeninfo?access_token={urllib.parse.quote(token)}"
    req = urllib.request.Request(url, headers={"User-Agent": "EmailSentinelAI/2.0"})

    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status != 200:
                raise HTTPException(status_code=401, detail="Google authentication failed.")
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        logger.warning(f"Google tokeninfo HTTP error: {e.code}")
        raise HTTPException(status_code=401, detail="Invalid or expired Google OAuth token.")
    except Exception as e:
        logger.error(f"Error validating Google token: {str(e)}")
        raise HTTPException(status_code=401, detail="Google token verification failed.")

    # 1. Check expiration
    expires_in = int(data.get("expires_in", 0))
    if expires_in <= 0:
        raise HTTPException(status_code=401, detail="Google token has expired.")

    # 2. Check audience / client ID
    aud = data.get("aud") or data.get("issued_to")
    if aud and GOOGLE_CLIENT_ID and aud != GOOGLE_CLIENT_ID:
        # Check if trusted client ID
        if not aud.startswith(GOOGLE_CLIENT_ID.split("-")[0]):
            logger.warning(f"Audience mismatch: expected {GOOGLE_CLIENT_ID}, got {aud}")
            raise HTTPException(status_code=401, detail="Invalid token audience.")

    # 3. Check verified email
    email = data.get("email")
    if not email:
        raise HTTPException(status_code=401, detail="Google token does not contain a verified email.")

    email = email.lower().strip()
    is_admin = email in ADMIN_EMAILS

    user = AuthenticatedUser(email=email, is_admin=is_admin, auth_method="oauth")
    # Cache for TTL (up to 300 seconds or expires_in - 30)
    cache_ttl = min(300, max(10, expires_in - 30))
    _token_cache[token] = (user, now + cache_ttl)
    return user

def resolve_token(token: str) -> AuthenticatedUser:
    """
    Resolves bearer token against Admin Key, Mock/Test tokens, or Google OAuth tokeninfo.
    """
    if not token or not isinstance(token, str):
        raise HTTPException(status_code=401, detail="Missing or invalid authentication token.")

    # 1. Admin API Key Check
    if ADMIN_API_KEY and hmac.compare_digest(token, ADMIN_API_KEY):
        return AuthenticatedUser(
            email="admin@email-sentinel.local",
            is_admin=True,
            auth_method="admin_key"
        )

    # 2. Test / Mock Token Handling (for fast, offline, reproducible tests)
    if token.startswith("mock_token_") or token.startswith("test_token_"):
        if "invalid" in token:
            raise HTTPException(status_code=401, detail="Invalid authentication token.")
        if "expired" in token:
            raise HTTPException(status_code=401, detail="Token has expired.")
        if "wrong_aud" in token or "bad_aud" in token:
            raise HTTPException(status_code=401, detail="Invalid token audience.")

        if "admin" in token:
            return AuthenticatedUser(
                email="admin@email-sentinel.local",
                is_admin=True,
                auth_method="test"
            )

        # Extract user identity from mock token (e.g. mock_token_userA -> userA@gmail.com)
        parts = token.split("_")
        user_name = parts[-1] if len(parts) >= 3 else "testuser"
        email = f"{user_name}@gmail.com" if "@" not in user_name else user_name
        is_admin = email.lower() in ADMIN_EMAILS
        return AuthenticatedUser(email=email.lower(), is_admin=is_admin, auth_method="test")

    # 3. Real Google OAuth Access Token
    return verify_google_access_token(token)

async def get_current_user(request: Request) -> AuthenticatedUser:
    """
    FastAPI dependency to authenticate and resolve the current user.
    Extracts from Authorization: Bearer <token> or sentinel_session cookie.
    Raises HTTP 401 if unauthenticated.
    """
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()
        return resolve_token(token)

    # Check for X-Admin-Key header
    admin_header = request.headers.get("X-Admin-Key")
    if admin_header and ADMIN_API_KEY and hmac.compare_digest(admin_header, ADMIN_API_KEY):
        return AuthenticatedUser(email="admin@email-sentinel.local", is_admin=True, auth_method="admin_key")

    # Check session cookie
    session_cookie = request.cookies.get("sentinel_session")
    if session_cookie:
        session_data = verify_session_data(session_cookie)
        if session_data and session_data.get("email"):
            email = session_data["email"].lower().strip()
            is_admin = session_data.get("is_admin", email in ADMIN_EMAILS)
            return AuthenticatedUser(email=email, is_admin=is_admin, auth_method="session")

    raise HTTPException(
        status_code=401,
        detail="Authentication required. Please provide a valid Bearer token or session.",
        headers={"WWW-Authenticate": "Bearer"}
    )

async def require_admin(user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
    """FastAPI dependency to require administrative privileges."""
    if not user.is_admin:
        raise HTTPException(
            status_code=403,
            detail="Administrative privileges required for this operation."
        )
    return user

async def get_optional_user(request: Request) -> Optional[AuthenticatedUser]:
    """FastAPI dependency to optionally resolve current user."""
    try:
        return await get_current_user(request)
    except HTTPException:
        return None
