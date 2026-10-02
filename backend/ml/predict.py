import os
import json
import logging
import joblib
from typing import Optional
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

class SpamClassifier:
    """
    Inference layer for Email Spam Detection.
    Loads and runs ONLY the active production model version (status = 'production').
    """

    def __init__(self, model_dir: Optional[str] = None, active_version: Optional[str] = None):
        if model_dir is None:
            model_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'models'))
            
        self.model_dir = model_dir
        self.active_version = active_version
        self.model = None
        self.metadata = {}
        
        self.load_model()
        
    def resolve_active_version(self, db_session: Optional[Session] = None) -> str:
        """
        Determines the active production model version from DB or defaults to 'v1'.
        Only model_versions with status == 'production' may be selected.
        """
        if self.active_version:
            return self.active_version

        if db_session is not None:
            try:
                from backend.database.repository import Repository
                repo = Repository(db_session)
                prod_model = repo.get_active_production_model()
                if prod_model and prod_model.version:
                    return prod_model.version
            except Exception as e:
                logger.warning(f"Could not query active production model from DB: {str(e)}")

        # Try opening DB session if available
        try:
            from backend.database.database import SessionLocal
            db = SessionLocal()
            try:
                from backend.database.repository import Repository
                repo = Repository(db)
                prod_model = repo.get_active_production_model()
                if prod_model and prod_model.version:
                    return prod_model.version
            finally:
                db.close()
        except Exception:
            pass

        return "v1"

    def load_model(self, db_session: Optional[Session] = None, model_dir: Optional[str] = None):
        """
        Loads the active production model file and metadata.
        Fails safely if the active production model file cannot be found/loaded.
        Never silently falls back to candidate models.
        """
        if model_dir:
            self.model_dir = model_dir

        version = self.resolve_active_version(db_session)
        model_filename = f"spam_model_{version}.joblib"
        metadata_filename = f"metadata_{version}.json"

        model_path = os.path.join(self.model_dir, model_filename)
        metadata_path = os.path.join(self.model_dir, metadata_filename)

        if not os.path.exists(model_path):
            # Fallback check for v1 if specific file not found
            if version != "v1":
                raise FileNotFoundError(f"Active production model file for '{version}' not found at {model_path}. Refusing to load unvalidated candidate model.")
            else:
                raise FileNotFoundError(f"Production model file not found at {model_path}")

        try:
            self.model = joblib.load(model_path)
            
            if os.path.exists(metadata_path):
                with open(metadata_path, 'r') as f:
                    self.metadata = json.load(f)
            else:
                self.metadata = {"version": version}

            self.active_version = version
            logger.info(f"Successfully loaded active production model: {version}")

        except Exception as e:
            logger.error(f"Failed to load active production model version '{version}': {str(e)}")
            raise

    def reload_active_model(self, db_session: Optional[Session] = None, model_dir: Optional[str] = None):
        """Reloads active model after promotion or rollback."""
        if model_dir:
            self.model_dir = model_dir
        self.active_version = None
        self.load_model(db_session=db_session, model_dir=model_dir)

    def predict_email(self, subject: str, body: str, sender: str = None) -> dict:
        """
        Combines email fields into a single text block for the NLP pipeline.
        Predicts using the active production model.
        """
        if self.model is None:
            raise RuntimeError("Production model is not loaded.")
            
        parts = []
        if subject:
            parts.append(subject)
        if body:
            parts.append(body)
            
        combined_text = " ".join(parts).strip()
        
        prediction = self.model.predict([combined_text])[0]
        
        # LinearSVC decision function score
        if hasattr(self.model, "decision_function"):
            decision_score = float(self.model.decision_function([combined_text])[0])
        else:
            decision_score = 0.0
            
        # Standardize prediction string ("SPAM" or "HAM")
        label = "SPAM" if (prediction == 1 or str(prediction).upper() == "SPAM") else "HAM"
        
        return {
            "classification": label,
            "model_version": self.metadata.get("version", self.active_version or "v1"),
            "decision_score": decision_score
        }

# Singleton instance for the API to use
classifier_instance = None

def get_classifier() -> SpamClassifier:
    global classifier_instance
    if classifier_instance is None:
        classifier_instance = SpamClassifier()
    return classifier_instance
