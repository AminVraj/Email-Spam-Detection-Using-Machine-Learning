from typing import List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from backend.database.models import Feedback, Email, Prediction, ModelVersion
from backend.nlp.preprocessing import clean_text

class FeedbackValidator:
    """
    Dedicated feedback validation layer for Adaptive Learning.
    Validates user feedback against strict quality rules before inclusion in model training datasets.
    """
    
    VALID_LABELS = {"SPAM", "HAM"}

    def __init__(self, db: Session):
        self.db = db

    def validate_all_feedback(self, already_used_feedback_ids: set = None) -> Dict[str, Any]:
        """
        Validates all recorded feedback records in the database.
        
        Returns a detailed report containing:
        - valid_feedback: list of eligible feedback dicts
        - invalid_feedback: list of ineligible feedback dicts with reasons
        - summary statistics
        """
        if already_used_feedback_ids is None:
            already_used_feedback_ids = set()

        feedbacks = self.db.query(Feedback).all()

        valid_feedback = []
        invalid_feedback = []

        seen_email_ids = set()
        seen_content_labels: Dict[str, set] = {} # maps clean text -> set of labels

        # Pass 1: Content conflict detection across all feedback
        content_map: Dict[str, List[Feedback]] = {}
        for fb in feedbacks:
            email = self.db.query(Email).filter(Email.id == fb.email_id).first()
            if email:
                combined_text = ((email.subject or "") + " " + (email.body_text or "")).strip()
                cleaned = clean_text(combined_text)
                if cleaned:
                    if cleaned not in seen_content_labels:
                        seen_content_labels[cleaned] = set()
                    seen_content_labels[cleaned].add(fb.user_label.upper())

        # Pass 2: Validation of individual records
        for fb in feedbacks:
            # Check 1: Valid user label
            if not fb.user_label or fb.user_label.upper() not in self.VALID_LABELS:
                invalid_feedback.append({
                    "feedback_id": fb.id,
                    "email_id": fb.email_id,
                    "reason": f"Invalid user label: '{fb.user_label}'. Must be 'SPAM' or 'HAM'."
                })
                continue

            # Check 2: Email exists
            email = self.db.query(Email).filter(Email.id == fb.email_id).first()
            if not email:
                invalid_feedback.append({
                    "feedback_id": fb.id,
                    "email_id": fb.email_id,
                    "reason": f"Email with ID {fb.email_id} not found."
                })
                continue

            # Check 3 & 7: Email contains usable training text (subject or body not empty)
            subject_str = (email.subject or "").strip()
            body_str = (email.body_text or "").strip()
            combined_text = (subject_str + " " + body_str).strip()
            cleaned_text = clean_text(combined_text)
            
            if not combined_text or not cleaned_text:
                invalid_feedback.append({
                    "feedback_id": fb.id,
                    "email_id": fb.email_id,
                    "reason": "Email subject and body are both empty or contain no usable text."
                })
                continue

            # Check 4: Linked to a valid prediction
            prediction = self.db.query(Prediction).filter(Prediction.id == fb.prediction_id).first()
            if not prediction:
                invalid_feedback.append({
                    "feedback_id": fb.id,
                    "email_id": fb.email_id,
                    "reason": f"Prediction with ID {fb.prediction_id} not found."
                })
                continue

            # Check 5: Duplicate check (if same email_id seen multiple times in this batch)
            if fb.email_id in seen_email_ids:
                invalid_feedback.append({
                    "feedback_id": fb.id,
                    "email_id": fb.email_id,
                    "reason": f"Duplicate feedback record for email ID {fb.email_id}."
                })
                continue
            seen_email_ids.add(fb.email_id)

            # Check 6: Conflicting labels detection (same content labeled as both SPAM and HAM)
            if len(seen_content_labels.get(cleaned_text, set())) > 1:
                invalid_feedback.append({
                    "feedback_id": fb.id,
                    "email_id": fb.email_id,
                    "reason": "Conflicting feedback labels detected for identical email text. Marked for review."
                })
                continue

            # Check 8: Not already included in a previous training dataset
            if fb.id in already_used_feedback_ids:
                invalid_feedback.append({
                    "feedback_id": fb.id,
                    "email_id": fb.email_id,
                    "reason": "Feedback already used in a previous model training version."
                })
                continue

            # Check 9: Preserve original prediction and user label for auditing
            valid_feedback.append({
                "feedback_id": fb.id,
                "email_id": fb.email_id,
                "prediction_id": fb.prediction_id,
                "text": combined_text,
                "label": fb.user_label.upper(),
                "original_prediction": fb.original_prediction,
                "model_version": fb.model_version,
                "created_at": fb.created_at.isoformat() if fb.created_at else None
            })

        duplicate_count = sum(1 for inv in invalid_feedback if "Duplicate" in inv["reason"])
        conflicting_count = sum(1 for inv in invalid_feedback if "Conflicting" in inv["reason"])

        return {
            "total_feedback": len(feedbacks),
            "valid_count": len(valid_feedback),
            "invalid_count": len(invalid_feedback),
            "duplicate_count": duplicate_count,
            "conflicting_count": conflicting_count,
            "valid_feedback": valid_feedback,
            "invalid_feedback": invalid_feedback
        }
