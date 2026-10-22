import hashlib
import json
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from datetime import datetime
from backend.database.models import Email, Prediction, Feedback, ModelVersion

class Repository:
    def __init__(self, db: Session):
        self.db = db

    def _hash_text(self, text: str) -> str:
        return hashlib.sha256(text.encode('utf-8')).hexdigest()

    def check_email_exists(self, provider_message_id: str, account_email: str = None) -> bool:
        if not provider_message_id:
            return False
        query = self.db.query(Email).filter(Email.provider_message_id == provider_message_id)
        if account_email:
            query = query.filter(Email.account_email == account_email)
        return query.first() is not None

    def get_email_by_provider_message_id(self, provider_message_id: str, account_email: str = None):
        if not provider_message_id:
            return None
        query = self.db.query(Email).filter(Email.provider_message_id == provider_message_id)
        if account_email:
            query = query.filter(Email.account_email == account_email)
        return query.first()

    def get_email_by_body_hash(self, body_hash: str):
        if not body_hash:
            return None
        return self.db.query(Email).filter(Email.body_hash == body_hash).first()

    def record_email_and_prediction(self, subject: str, body: str, sender: str = None,
                                    classification: str = "HAM", decision_score: float = 0.0, model_version: str = "v1",
                                    provider: str = "api", provider_message_id: str = None, provider_category: str = "PRIMARY",
                                    received_at: datetime = None, account_email: str = None):
        body_hash = self._hash_text((subject or "") + (body or ""))

        # Deduplication check: check provider_message_id and account_email if provided
        if provider_message_id:
            existing = self.get_email_by_provider_message_id(provider_message_id, account_email=account_email)
            if existing:
                prediction = self.db.query(Prediction).filter(Prediction.email_id == existing.id).first()
                if prediction:
                    return existing.id, prediction.id
                # Existing email record is missing prediction (inconsistent state); repair prediction atomically
                try:
                    prediction = Prediction(
                        email_id=existing.id,
                        classification=classification,
                        decision_score=decision_score,
                        model_version=model_version
                    )
                    self.db.add(prediction)
                    self.db.commit()
                    self.db.refresh(prediction)
                    return existing.id, prediction.id
                except Exception:
                    self.db.rollback()
                    raise

        rec_time = received_at if received_at else datetime.utcnow()

        # Atomic transaction: Insert both Email and Prediction in a single commit block
        try:
            email = Email(
                provider=provider,
                provider_category=provider_category,
                provider_message_id=provider_message_id,
                account_email=account_email,
                sender=sender,
                subject=subject,
                body_hash=body_hash,
                body_text=body,
                received_at=rec_time
            )
            self.db.add(email)
            self.db.flush()  # Obtain email.id without committing the transaction

            prediction = Prediction(
                email_id=email.id,
                classification=classification,
                decision_score=decision_score,
                model_version=model_version
            )
            self.db.add(prediction)
            self.db.commit()  # Atomic commit of both records
            self.db.refresh(email)
            self.db.refresh(prediction)

            return email.id, prediction.id
        except IntegrityError:
            self.db.rollback()
            # If concurrent insert already created this provider message, reuse it
            if provider_message_id:
                existing = self.get_email_by_provider_message_id(provider_message_id, account_email=account_email)
                if existing:
                    pred = self.db.query(Prediction).filter(Prediction.email_id == existing.id).first()
                    if pred:
                        return existing.id, pred.id
            raise
        except Exception:
            self.db.rollback()
            raise

    def record_feedback(self, email_id: int, user_label: str, account_email: str = None) -> dict:
        if user_label not in ["SPAM", "HAM"]:
            raise ValueError("user_label must be SPAM or HAM")

        # Verify email exists and account owns it
        email = self.db.query(Email).filter(Email.id == email_id).first()
        if not email:
            raise ValueError(f"Email with id {email_id} not found")

        if account_email and email.account_email and email.account_email.lower() != account_email.lower():
            raise PermissionError(f"Unauthorized: Email {email_id} belongs to another user account")

        # Verify prediction exists
        prediction = self.db.query(Prediction).filter(Prediction.email_id == email_id).first()
        if not prediction:
            raise ValueError(f"No prediction found for email_id {email_id}")

        # Prevent duplicate feedback
        existing_feedback = self.db.query(Feedback).filter(Feedback.email_id == email_id).first()
        if existing_feedback:
            raise ValueError(f"Feedback already recorded for email_id {email_id}")

        try:
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
        except Exception:
            self.db.rollback()
            raise

    def list_emails(self, limit: int = 50, account_email: str = None) -> list:
        query = self.db.query(Email)
        if account_email:
            query = query.filter(Email.account_email == account_email)
        return query.order_by(Email.received_at.desc()).limit(limit).all()

    def get_email_details(self, email_id: int, account_email: str = None) -> dict:
        email = self.db.query(Email).filter(Email.id == email_id).first()
        if not email:
            return None
        if account_email and email.account_email and email.account_email.lower() != account_email.lower():
            raise PermissionError(f"Access denied: Email {email_id} belongs to another account")
        prediction = self.db.query(Prediction).filter(Prediction.email_id == email_id).first()
        feedback = self.db.query(Feedback).filter(Feedback.email_id == email_id).first()
        return {
            "email": email,
            "prediction": prediction,
            "feedback": feedback
        }

    def get_statistics(self, account_email: str = None) -> dict:
        if account_email:
            total_predictions = self.db.query(Prediction).join(Email).filter(Email.account_email == account_email).count()
            spam_predictions = self.db.query(Prediction).join(Email).filter(
                Prediction.classification == "SPAM",
                Email.provider_category != "PROMOTIONS",
                Email.account_email == account_email
            ).count()
            ham_predictions = self.db.query(Prediction).join(Email).filter(
                Prediction.classification == "HAM",
                Email.provider_category != "PROMOTIONS",
                Email.account_email == account_email
            ).count()
            promotions_count = self.db.query(Email).filter(
                Email.provider_category == "PROMOTIONS",
                Email.account_email == account_email
            ).count()

            total_feedback = self.db.query(Feedback).join(Email).filter(Email.account_email == account_email).count()
            user_corrections = self.db.query(Feedback).join(Email).filter(
                Feedback.original_prediction != Feedback.user_label,
                Email.account_email == account_email
            ).count()

            tp_confirmed = self.db.query(Feedback).join(Email).filter(
                Feedback.original_prediction == "SPAM", Feedback.user_label == "SPAM",
                Email.account_email == account_email
            ).count()
            tn_confirmed = self.db.query(Feedback).join(Email).filter(
                Feedback.original_prediction == "HAM", Feedback.user_label == "HAM",
                Email.account_email == account_email
            ).count()
            fp_observed = self.db.query(Feedback).join(Email).filter(
                Feedback.original_prediction == "SPAM", Feedback.user_label == "HAM",
                Email.account_email == account_email
            ).count()
            fn_observed = self.db.query(Feedback).join(Email).filter(
                Feedback.original_prediction == "HAM", Feedback.user_label == "SPAM",
                Email.account_email == account_email
            ).count()
        else:
            total_predictions = self.db.query(Prediction).count()
            spam_predictions = self.db.query(Prediction).join(Email).filter(Prediction.classification == "SPAM", Email.provider_category != "PROMOTIONS").count()
            ham_predictions = self.db.query(Prediction).join(Email).filter(Prediction.classification == "HAM", Email.provider_category != "PROMOTIONS").count()
            promotions_count = self.db.query(Email).filter(Email.provider_category == "PROMOTIONS").count()

            total_feedback = self.db.query(Feedback).count()
            user_corrections = self.db.query(Feedback).filter(Feedback.original_prediction != Feedback.user_label).count()

            tp_confirmed = self.db.query(Feedback).filter(
                Feedback.original_prediction == "SPAM", Feedback.user_label == "SPAM"
            ).count()
            tn_confirmed = self.db.query(Feedback).filter(
                Feedback.original_prediction == "HAM", Feedback.user_label == "HAM"
            ).count()
            fp_observed = self.db.query(Feedback).filter(
                Feedback.original_prediction == "SPAM", Feedback.user_label == "HAM"
            ).count()
            fn_observed = self.db.query(Feedback).filter(
                Feedback.original_prediction == "HAM", Feedback.user_label == "SPAM"
            ).count()

        active_model = self.get_active_production_model()
        current_version = active_model.version if active_model else "v1"

        return {
            "total_predictions": total_predictions,
            "spam_predictions": spam_predictions,
            "ham_predictions": ham_predictions,
            "promotions_count": promotions_count,
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
            "model_version": current_version,
            "account_scope": account_email or "all"
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

