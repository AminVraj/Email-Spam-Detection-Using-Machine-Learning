import hashlib
import json
from sqlalchemy.orm import Session
from datetime import datetime
from backend.database.models import Email, Prediction, Feedback, ModelVersion

class Repository:
    def __init__(self, db: Session):
        self.db = db

    def _hash_text(self, text: str) -> str:
        return hashlib.sha256(text.encode('utf-8')).hexdigest()

    def check_email_exists(self, provider_message_id: str) -> bool:
        if not provider_message_id:
            return False
        return self.db.query(Email).filter(Email.provider_message_id == provider_message_id).first() is not None

    def record_email_and_prediction(self, subject: str, body: str, sender: str, 
                                    classification: str, decision_score: float, model_version: str,
                                    provider: str = "api", provider_message_id: str = None):
        # 1. Create email record
        body_hash = self._hash_text((subject or "") + (body or ""))
        
        email = Email(
            provider=provider,
            provider_message_id=provider_message_id,
            sender=sender,
            subject=subject,
            body_hash=body_hash,
            body_text=body, # Kept for retraining; clear privacy implications noted in models
            received_at=datetime.utcnow()
        )
        self.db.add(email)
        self.db.commit()
        self.db.refresh(email)
        
        # 2. Create prediction record
        prediction = Prediction(
            email_id=email.id,
            classification=classification,
            decision_score=decision_score,
            model_version=model_version
        )
        self.db.add(prediction)
        self.db.commit()
        self.db.refresh(prediction)
        
        return email.id, prediction.id

    def record_feedback(self, email_id: int, user_label: str) -> dict:
        if user_label not in ["SPAM", "HAM"]:
            raise ValueError("user_label must be SPAM or HAM")
            
        # Verify email exists
        email = self.db.query(Email).filter(Email.id == email_id).first()
        if not email:
            raise ValueError(f"Email with id {email_id} not found")
            
        # Verify prediction exists
        prediction = self.db.query(Prediction).filter(Prediction.email_id == email_id).first()
        if not prediction:
            raise ValueError(f"No prediction found for email_id {email_id}")
            
        # Prevent duplicate feedback
        existing_feedback = self.db.query(Feedback).filter(Feedback.email_id == email_id).first()
        if existing_feedback:
            raise ValueError(f"Feedback already recorded for email_id {email_id}")
            
        feedback = Feedback(
            email_id=email.id,
            prediction_id=prediction.id,
            original_prediction=prediction.classification,
            user_label=user_label,
            model_version=prediction.model_version
        )
        self.db.add(feedback)
        self.db.commit()
        self.db.refresh(feedback)
        
        return {
            "status": "recorded",
            "email_id": email.id,
            "original_prediction": prediction.classification,
            "user_label": user_label
        }

    def list_emails(self, limit: int = 50) -> list:
        return self.db.query(Email).order_by(Email.received_at.desc()).limit(limit).all()

    def get_email_details(self, email_id: int) -> dict:
        email = self.db.query(Email).filter(Email.id == email_id).first()
        if not email:
            return None
        prediction = self.db.query(Prediction).filter(Prediction.email_id == email_id).first()
        feedback = self.db.query(Feedback).filter(Feedback.email_id == email_id).first()
        return {
            "email": email,
            "prediction": prediction,
            "feedback": feedback
        }

    def get_statistics(self) -> dict:
        total_predictions = self.db.query(Prediction).count()
        spam_predictions = self.db.query(Prediction).filter(Prediction.classification == "SPAM").count()
        ham_predictions = self.db.query(Prediction).filter(Prediction.classification == "HAM").count()
        
        total_feedback = self.db.query(Feedback).count()
        user_corrections = self.db.query(Feedback).filter(Feedback.original_prediction != Feedback.user_label).count()
        
        # Predicted SPAM, user said SPAM (True Positive)
        tp_confirmed = self.db.query(Feedback).filter(
            Feedback.original_prediction == "SPAM", Feedback.user_label == "SPAM"
        ).count()
        
        # Predicted HAM, user said HAM (True Negative)
        tn_confirmed = self.db.query(Feedback).filter(
            Feedback.original_prediction == "HAM", Feedback.user_label == "HAM"
        ).count()

        # Predicted SPAM, user said HAM (False Positive)
        fp_observed = self.db.query(Feedback).filter(
            Feedback.original_prediction == "SPAM", Feedback.user_label == "HAM"
        ).count()

        # Predicted HAM, user said SPAM (False Negative)
        fn_observed = self.db.query(Feedback).filter(
            Feedback.original_prediction == "HAM", Feedback.user_label == "SPAM"
        ).count()
        
        active_model = self.get_active_production_model()
        current_version = active_model.version if active_model else "v1"

        return {
            "total_predictions": total_predictions,
            "spam_predictions": spam_predictions,
            "ham_predictions": ham_predictions,
            "total_feedback": total_feedback,
            "user_corrections": user_corrections,
            "predicted_spam_confirmed_by_user": tp_confirmed,
            "predicted_ham_confirmed_by_user": tn_confirmed,
            "user_feedback_observed_outcomes": {
                "description": "User-feedback-based observed outcomes",
                "true_positives": tp_confirmed,
                "true_negatives": tn_confirmed,
                "false_positives": fp_observed,
                "false_negatives": fn_observed,
                "corrections": user_corrections
            },
            "model_version": current_version
        }

    def get_active_production_model(self) -> ModelVersion:
        """Fetch the active production model version record."""
        return self.db.query(ModelVersion).filter(ModelVersion.status == "production").order_by(ModelVersion.training_timestamp.desc()).first()

    def get_model_version(self, version: str) -> ModelVersion:
        """Fetch model version record by version string."""
        return self.db.query(ModelVersion).filter(ModelVersion.version == version).first()

    def list_model_versions(self) -> list:
        """List all model versions ordered by training timestamp."""
        return self.db.query(ModelVersion).order_by(ModelVersion.training_timestamp.desc()).all()

    def register_model_version(self, version: str, algorithm: str, features: dict, metrics: dict, 
                               timestamp: str, status: str = "candidate", 
                               training_data_summary: dict = None, feedback_count_used: int = 0, 
                               parent_model_version: str = None) -> ModelVersion:
        """Register or update a model version record."""
        ts = datetime.fromisoformat(timestamp) if isinstance(timestamp, str) else timestamp
        existing = self.db.query(ModelVersion).filter(ModelVersion.version == version).first()
        
        data_summary_str = json.dumps(training_data_summary) if training_data_summary else None
        features_str = json.dumps(features) if isinstance(features, (dict, list)) else features
        metrics_str = json.dumps(metrics) if isinstance(metrics, (dict, list)) else metrics

        if existing:
            existing.algorithm = algorithm
            existing.feature_configuration = features_str
            existing.metrics = metrics_str
            existing.training_timestamp = ts
            existing.status = status
            existing.training_data_summary = data_summary_str
            existing.feedback_count_used = feedback_count_used
            existing.parent_model_version = parent_model_version
            mv = existing
        else:
            mv = ModelVersion(
                version=version,
                algorithm=algorithm,
                feature_configuration=features_str,
                metrics=metrics_str,
                training_timestamp=ts,
                status=status,
                training_data_summary=data_summary_str,
                feedback_count_used=feedback_count_used,
                parent_model_version=parent_model_version
            )
            self.db.add(mv)
            
        self.db.commit()
        self.db.refresh(mv)
        return mv

    def set_model_status(self, version: str, status: str) -> ModelVersion:
        """Update model status for a version."""
        mv = self.get_model_version(version)
        if not mv:
            raise ValueError(f"Model version {version} not found")
        mv.status = status
        self.db.commit()
        self.db.refresh(mv)
        return mv

    def promote_model_version(self, version: str) -> ModelVersion:
        """Promote specified candidate model to production, archiving previous production models."""
        target = self.get_model_version(version)
        if not target:
            raise ValueError(f"Model version {version} not found")
            
        # Set all current production models to archived
        current_prods = self.db.query(ModelVersion).filter(ModelVersion.status == "production").all()
        for prod in current_prods:
            if prod.version != version:
                prod.status = "archived"
                
        target.status = "production"
        self.db.commit()
        self.db.refresh(target)
        return target

    def rollback_model_version(self, target_version: str) -> ModelVersion:
        """Rollback active production model to target_version."""
        target = self.get_model_version(target_version)
        if not target:
            raise ValueError(f"Target model version {target_version} not found in database")
            
        # Set current production model to archived
        current_prods = self.db.query(ModelVersion).filter(ModelVersion.status == "production").all()
        for prod in current_prods:
            if prod.version != target_version:
                prod.status = "archived"
                
        target.status = "production"
        self.db.commit()
        self.db.refresh(target)
        return target

