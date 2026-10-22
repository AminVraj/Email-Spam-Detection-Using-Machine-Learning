import os
import json
import logging
from dotenv import load_dotenv
from typing import Optional, Dict, Any

# Load environment variables from .env file securely
load_dotenv()
import time
from fastapi import FastAPI, HTTPException, Request, Response, Depends, UploadFile, File
from fastapi.responses import JSONResponse
import pytesseract
from PIL import Image
import io
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.config import ADAPTIVE_MIN_FEEDBACK, MODELS_DIR, CORS_ORIGINS, ADMIN_EMAILS
from backend.security.auth import (
    get_current_user,
    require_admin,
    get_optional_user,
    resolve_token,
    sign_session_data,
    AuthenticatedUser
)
from backend.ml.predict import get_classifier
from backend.database.database import init_db, get_db
from backend.database.repository import Repository
from backend.ml.feedback_validator import FeedbackValidator
from backend.ml.model_governance import ModelGovernance
from training.train_adaptive import train_candidate_model

from backend.email.normalizer import normalize_email_body
from backend.content.bad_word_detector import BadWordDetector

bad_word_detector = BadWordDetector()

# Setup structured logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Email Spam Detection API",
    description="Adaptive NLP-based Email Spam Detection System with Controlled Model Evolution",
    version="2.0.0"
)

# Secure CORS: Disallow wildcard with credentials, allow specific configured origins & extension pattern
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_origin_regex=r"^chrome-extension://.*$",
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Configure Tesseract path
tesseract_cmd = os.getenv("TESSERACT_CMD")
if tesseract_cmd:
    pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
elif os.name == 'nt':
    # Sensible Windows fallbacks
    win_paths = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\Tesseract-OCR\tesseract.exe")
    ]
    for p in win_paths:
        if os.path.exists(p):
            pytesseract.pytesseract.tesseract_cmd = p
            break

# Exception Handler to avoid exposing stack traces
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception occurred")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error"}
    )

from datetime import datetime

class EmailRequest(BaseModel):
    subject: Optional[str] = Field(default="", description="Email subject")
    body: Optional[str] = Field(default="", description="Email body content")
    sender: Optional[str] = Field(default=None, description="Email sender address")
    provider: Optional[str] = Field(default="api", description="Email provider e.g. gmail")
    provider_message_id: Optional[str] = Field(default=None, description="Message ID from provider")
    provider_category: Optional[str] = Field(default="PRIMARY", description="Provider category")
    received_at: Optional[str] = Field(default=None, description="ISO timestamp when email was received")
    account_email: Optional[str] = Field(default=None, description="Authenticated Gmail account email address")

class PredictionResponse(BaseModel):
    classification: str
    model_version: str
    decision_score: float
    email_id: Optional[int] = None

class FeedbackRequest(BaseModel):
    email_id: int
    user_label: str

class CandidateTrainRequest(BaseModel):
    candidate_version: Optional[str] = Field(default="v2", description="Candidate model version string")
    min_feedback_override: Optional[int] = Field(default=None, description="Optional override for min feedback threshold")

class RollbackRequest(BaseModel):
    target_version: Optional[str] = Field(default="v1", description="Target model version to rollback to")

@app.on_event("startup")
async def startup_event():
    logger.info("Starting up API, initializing database and loading active production model...")
    try:
        init_db()
        # Seed v1 in model_versions table if database is fresh
        from backend.database.database import SessionLocal
        db = SessionLocal()
        try:
            repo = Repository(db)
            if not repo.get_active_production_model():
                repo.register_model_version(
                    version="v1",
                    algorithm="Advanced Linear SVM",
                    features={"word_tfidf": "Unigram, Bigram, Trigram", "char_tfidf": "Char 2-5 gram"},
                    metrics={"Accuracy": 0.9919, "Spam_Precision": 1.0, "Spam_Recall": 0.9396, "Spam_F1": 0.9689},
                    timestamp="2026-09-30T13:37:05.360707",
                    status="production"
                )
        finally:
            db.close()

        classifier = get_classifier()
        classifier.reload_active_model()
    except Exception as e:
        logger.error(f"Startup failed: {str(e)}")

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.get("/model/info")
async def model_info(db: Session = Depends(get_db)):
    try:
        classifier = get_classifier()
        classifier.reload_active_model(db_session=db)
        safe_metadata = {
            "version": classifier.metadata.get("version"),
            "algorithm": classifier.metadata.get("algorithm"),
            "status": "production",
            "feature_configuration": classifier.metadata.get("feature_configuration"),
            "evaluation_metrics": classifier.metadata.get("evaluation_metrics"),
            "training_timestamp": classifier.metadata.get("training_timestamp")
        }
        return safe_metadata
    except Exception as e:
        logger.error(f"Error fetching model info: {str(e)}")
        raise HTTPException(status_code=503, detail="Model information unavailable")

class SessionRequest(BaseModel):
    token: str

class DevLoginRequest(BaseModel):
    email: str
    is_admin: Optional[bool] = False

@app.post("/auth/session")
async def create_session(request: SessionRequest, response: Response):
    user = resolve_token(request.token)
    session_data = {
        "email": user.email,
        "is_admin": user.is_admin,
        "exp": time.time() + 86400 * 7
    }
    cookie_val = sign_session_data(session_data)
    response.set_cookie(
        key="sentinel_session",
        value=cookie_val,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=86400 * 7
    )
    return {
        "status": "authenticated",
        "email": user.email,
        "is_admin": user.is_admin
    }

@app.get("/auth/me")
async def get_me(user: AuthenticatedUser = Depends(get_current_user)):
    return {
        "email": user.email,
        "is_admin": user.is_admin,
        "auth_method": user.auth_method
    }

@app.post("/auth/logout")
async def logout(response: Response):
    response.delete_cookie("sentinel_session")
    return {"status": "logged_out"}

@app.post("/auth/dev-login")
async def dev_login(request: DevLoginRequest, response: Response):
    if os.getenv("ENVIRONMENT") == "production":
        raise HTTPException(status_code=403, detail="Dev login disabled in production")
    email = request.email.strip().lower()
    is_admin = request.is_admin or (email in ADMIN_EMAILS)
    session_data = {
        "email": email,
        "is_admin": is_admin,
        "exp": time.time() + 86400 * 7
    }
    cookie_val = sign_session_data(session_data)
    response.set_cookie(
        key="sentinel_session",
        value=cookie_val,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=86400 * 7
    )
    return {"status": "authenticated", "email": email, "is_admin": is_admin}

@app.post("/predict", response_model=PredictionResponse)
async def predict_email(
    request: EmailRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        # Check for account mismatch if client explicitly supplied account_email
        if request.account_email and request.account_email.lower().strip() != user.email.lower().strip():
            logger.warning(f"Account mismatch: token email {user.email} != payload email {request.account_email}")
            raise HTTPException(status_code=403, detail="Account mismatch: cannot submit emails for another account.")

        # Bind strictly to authenticated user identity
        account_email = user.email

        subject = request.subject.strip() if request.subject else ""
        raw_body = request.body.strip() if request.body else ""
        body = normalize_email_body(raw_body)

        if not subject and not body:
            raise HTTPException(status_code=400, detail="Email subject and body cannot both be empty.")

        if len(body) > 100000:
            raise HTTPException(status_code=400, detail="Email body exceeds maximum allowed length.")

        valid_categories = {"PRIMARY", "PROMOTIONS", "SOCIAL", "UPDATES", "FORUMS"}
        provider_cat = (request.provider_category or "PRIMARY").upper().strip()
        if provider_cat not in valid_categories:
            provider_cat = "PRIMARY"

        classifier = get_classifier()

        result = classifier.predict_email(
            subject=subject,
            body=body,
            sender=request.sender
        )

        rec_dt = None
        if request.received_at:
            try:
                rec_dt = datetime.fromisoformat(request.received_at.replace("Z", "+00:00"))
            except Exception:
                rec_dt = None

        # Save to database with deduplication scoped to authenticated user
        repo = Repository(db)
        email_id, _ = repo.record_email_and_prediction(
            subject=subject,
            body=body,
            sender=request.sender,
            classification=result["classification"],
            decision_score=result["decision_score"],
            model_version=result["model_version"],
            provider=request.provider or "api",
            provider_message_id=request.provider_message_id,
            provider_category=provider_cat,
            received_at=rec_dt,
            account_email=account_email
        )

        result["email_id"] = email_id

        logger.info(f"prediction_completed model_version={result['model_version']} classification={result['classification']} email_id={email_id} account={account_email}")

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during prediction: {str(e)}")
        raise HTTPException(status_code=500, detail="Prediction failed")

@app.post("/analyze-manual", response_model=PredictionResponse)
async def analyze_manual(request: EmailRequest):
    try:
        subject = request.subject.strip() if request.subject else ""
        raw_body = request.body.strip() if request.body else ""
        body = normalize_email_body(raw_body)

        if not subject and not body:
            raise HTTPException(status_code=400, detail="Email subject and body cannot both be empty.")

        if len(body) > 100000:
            raise HTTPException(status_code=400, detail="Email body exceeds maximum allowed length.")

        is_blocked, detected_count = bad_word_detector.check_text(body)
        if is_blocked:
            return JSONResponse(status_code=400, content={
                "blocked": True,
                "reason": "BAD_WORD_DETECTED",
                "detected_count": detected_count
            })

        classifier = get_classifier()

        result = classifier.predict_email(
            subject=subject,
            body=body,
            sender=request.sender
        )

        logger.info(f"manual_analysis_completed model_version={result['model_version']} classification={result['classification']}")

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during manual analysis: {str(e)}")
        raise HTTPException(status_code=500, detail="Manual analysis failed")

@app.post("/feedback")
async def submit_feedback(
    request: FeedbackRequest,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        repo = Repository(db)
        account_email = None if user.is_admin else user.email
        result = repo.record_feedback(request.email_id, request.user_label.upper(), account_email=account_email)
        logger.info(f"feedback_recorded email_id={request.email_id} user_label={request.user_label} user={user.email}")
        return result
    except PermissionError as pe:
        logger.warning(f"Cross-account feedback attempted: {str(pe)}")
        raise HTTPException(status_code=403, detail=str(pe))
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Error recording feedback: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to record feedback")

@app.get("/statistics")
async def get_statistics(
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        repo = Repository(db)
        account_email = None if user.is_admin else user.email
        return repo.get_statistics(account_email=account_email)
    except Exception as e:
        logger.error(f"Error getting statistics: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get statistics")

# --- EMAILS ENDPOINTS ---

@app.get("/emails")
async def get_emails(
    limit: int = 50,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        repo = Repository(db)
        account_email = None if user.is_admin else user.email
        emails = repo.list_emails(limit, account_email=account_email)
        res = []
        for e in emails:
            # Check for prediction
            pred = e.prediction

            classification = pred.classification if pred else "UNKNOWN"
            if getattr(e, "provider_category", "PRIMARY") == "PROMOTIONS":
                classification = "PROMOTION"

            res.append({
                "id": e.id,
                "sender": e.sender,
                "subject": e.subject,
                "received_at": e.received_at.isoformat() if e.received_at else None,
                "classification": classification,
                "provider_category": getattr(e, "provider_category", "PRIMARY"),
                "ml_prediction": pred.classification if pred else "UNKNOWN",
                "decision_score": pred.decision_score if pred else None,
                "model_version": pred.model_version if pred else "UNKNOWN",
            })
        return {"emails": res}
    except Exception as e:
        logger.error(f"Error getting emails: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get emails")

@app.get("/emails/{email_id}")
async def get_email_details(
    email_id: int,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    try:
        repo = Repository(db)
        account_email = None if user.is_admin else user.email
        data = repo.get_email_details(email_id, account_email=account_email)
        if not data:
            raise HTTPException(status_code=404, detail="Email not found")

        e = data["email"]
        p = data["prediction"]
        f = data["feedback"]

        classification = p.classification if p else "UNKNOWN"
        if getattr(e, "provider_category", "PRIMARY") == "PROMOTIONS":
            classification = "PROMOTION"

        return {
            "id": e.id,
            "sender": e.sender,
            "subject": e.subject,
            "body": normalize_email_body(e.body_text) if e.body_text else "",
            "received_at": e.received_at.isoformat() if e.received_at else None,
            "classification": classification,
            "provider_category": getattr(e, "provider_category", "PRIMARY"),
            "ml_prediction": p.classification if p else "UNKNOWN",
            "decision_score": p.decision_score if p else None,
            "model_version": p.model_version if p else "UNKNOWN",
            "feedback": {
                "user_label": f.user_label,
                "original_prediction": f.original_prediction
            } if f else None
        }
    except PermissionError as pe:
        logger.warning(f"Unauthorized email access attempt: {str(pe)}")
        raise HTTPException(status_code=403, detail=str(pe))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting email {email_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get email")

# --- PHASE 5: ADAPTIVE LEARNING & MODEL EVOLUTION ENDPOINTS ---

@app.get("/feedback/quality-report")
async def feedback_quality_report(
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns statistics on feedback quality and training readiness.
    Privacy preserving: Email contents are NEVER exposed.
    """
    try:
        validator = FeedbackValidator(db)
        val_report = validator.validate_all_feedback()

        eligible_count = val_report["valid_count"]
        min_required = ADAPTIVE_MIN_FEEDBACK

        return {
            "total_feedback": val_report["total_feedback"],
            "valid_feedback": eligible_count,
            "invalid_feedback": val_report["invalid_count"],
            "duplicate_feedback": val_report["duplicate_count"],
            "conflicting_feedback": val_report["conflicting_count"],
            "new_feedback_available": eligible_count,
            "minimum_required": min_required,
            "training_ready": eligible_count >= min_required
        }
    except Exception as e:
        logger.error(f"Error generating feedback quality report: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate feedback report")

@app.post("/models/train-candidate")
async def train_candidate_endpoint(
    request: Optional[CandidateTrainRequest] = None,
    admin: AuthenticatedUser = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Triggers adaptive candidate model training.
    Requires administrative privileges.
    """
    try:
        version = request.candidate_version if request and request.candidate_version else "v2"
        min_override = request.min_feedback_override if request else None

        result = train_candidate_model(
            db_session=db,
            candidate_version=version,
            min_feedback_override=min_override
        )

        if result.get("status") == "error":
            return JSONResponse(status_code=400, content=result)

        return result
    except Exception as e:
        logger.error(f"Error training candidate model: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Candidate training failed: {str(e)}")

@app.get("/models")
async def list_models(
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Lists all registered model versions and their metadata."""
    try:
        repo = Repository(db)
        versions = repo.list_model_versions()
        res = []
        for mv in versions:
            metrics_dict = json.loads(mv.metrics) if mv.metrics else {}
            res.append({
                "version": mv.version,
                "algorithm": mv.algorithm,
                "status": mv.status,
                "training_timestamp": mv.training_timestamp.isoformat() if mv.training_timestamp else None,
                "feedback_count_used": mv.feedback_count_used,
                "metrics": metrics_dict
            })
        return {"models": res}
    except Exception as e:
        logger.error(f"Error listing models: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to list models")

@app.get("/models/compare/{version}")
async def compare_candidate_endpoint(
    version: str,
    user: AuthenticatedUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Compares candidate model version against current production model (v1)."""
    try:
        v1_meta_path = os.path.join(MODELS_DIR, "metadata_v1.json")
        cand_meta_path = os.path.join(MODELS_DIR, f"metadata_{version}.json")

        if not os.path.exists(v1_meta_path):
            raise HTTPException(status_code=404, detail="Production v1 metadata not found")
        if not os.path.exists(cand_meta_path):
            raise HTTPException(status_code=404, detail=f"Candidate metadata for version '{version}' not found")

        with open(v1_meta_path, 'r') as f:
            v1_meta = json.load(f)
        with open(cand_meta_path, 'r') as f:
            cand_meta = json.load(f)

        v1_metrics = v1_meta.get("evaluation_metrics", {})
        cand_metrics = cand_meta.get("evaluation_metrics", {})

        comparison = ModelGovernance.compare_models(v1_metrics, cand_metrics)
        return {
            "production_version": "v1",
            "candidate_version": version,
            "comparison": comparison
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error comparing models: {str(e)}")
        raise HTTPException(status_code=500, detail="Model comparison failed")

@app.post("/models/{version}/promote")
async def promote_model_endpoint(
    version: str,
    admin: AuthenticatedUser = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Explicitly promotes candidate model version to production after governance checks.
    Requires administrative privileges.
    """
    try:
        result = ModelGovernance.promote_candidate(db, version)
        if result.get("status") == "rejected":
            return JSONResponse(status_code=400, content=result)
        return result
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        logger.error(f"Error promoting model {version}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Promotion failed: {str(e)}")

@app.post("/models/{version}/rollback")
async def rollback_model_endpoint(
    version: str,
    admin: AuthenticatedUser = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Rolls back active production model to specified version without retraining.
    Requires administrative privileges.
    """
    try:
        result = ModelGovernance.rollback_model(db, version)
        return result
    except FileNotFoundError as fnf:
        raise HTTPException(status_code=404, detail=str(fnf))
    except ValueError as ve:
        raise HTTPException(status_code=404, detail=str(ve))
    except Exception as e:
        logger.error(f"Error rolling back to version {version}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Rollback failed: {str(e)}")

# --- GMAIL ENDPOINTS ---

from backend.email.gmail import GmailProvider
from backend.email.service import EmailSyncService

@app.post("/gmail/sync")
async def sync_gmail(
    admin: AuthenticatedUser = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """
    Triggers IMAP sync for the server-configured Gmail account.
    Restricted to administrative users because IMAP uses a single server credential.
    """
    try:
        service = EmailSyncService(db)
        summary = service.sync_recent(limit=20)
        return summary
    except Exception as e:
        logger.error(f"Error during Gmail sync: {str(e)}")
        raise HTTPException(status_code=500, detail="Gmail sync failed")

@app.get("/gmail/auth/status")
async def gmail_auth_status(admin: AuthenticatedUser = Depends(require_admin)):
    try:
        provider = GmailProvider()
        is_authenticated = provider.authenticate()
        return {"authenticated": is_authenticated}
    except Exception as e:
        logger.error(f"Error checking Gmail auth status: {str(e)}")
        return {"authenticated": False}

@app.post("/ocr")
async def ocr_endpoint(file: UploadFile = File(...)):
    try:
        content = await file.read()
        file_size = len(content)

        # Development Logging
        logger.info(f"OCR Endpoint Invoked. Filename: {file.filename}, Content-Type: {file.content_type}, Size: {file_size} bytes")

        image = Image.open(io.BytesIO(content))

        try:
            text = pytesseract.image_to_string(image)
        except pytesseract.pytesseract.TesseractNotFoundError as e:
            logger.error(f"Tesseract is not installed or configured correctly: {e}")
            raise HTTPException(status_code=500, detail="Tesseract OCR engine is missing.")
        except Exception as e:
            logger.exception("Tesseract processing failed during image_to_string")
            raise HTTPException(status_code=500, detail="OCR processing failed")

        normalized_text = normalize_email_body(text)

        is_blocked, detected_count = bad_word_detector.check_text(normalized_text)
        if is_blocked:
            return JSONResponse(status_code=400, content={
                "blocked": True,
                "reason": "BAD_WORD_DETECTED",
                "detected_count": detected_count
            })

        # Log first 100 chars
        logger.info(f"OCR Result Preview (first 100 chars): {normalized_text[:100]}")

        return {"text": normalized_text}
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error during OCR endpoint processing")
        raise HTTPException(status_code=500, detail="OCR processing failed")
