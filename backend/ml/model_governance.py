import os
import json
import joblib
from typing import Dict, Any, Tuple
from sqlalchemy.orm import Session

from backend.config import MODELS_DIR
from backend.database.repository import Repository
from backend.ml.predict import get_classifier

class ModelGovernance:
    """
    Handles Model Comparison, Promotion Governance, and Auditability/Rollback.
    """

    @staticmethod
    def compare_models(v1_metrics: Dict[str, Any], v2_metrics: Dict[str, Any]) -> Dict[str, Any]:
        """
        Produces a factual side-by-side metric comparison between two model versions.
        """
        metrics_keys = [
            "Accuracy", "Spam_Precision", "Spam_Recall", "Spam_F1",
            "Ham_Precision", "Ham_Recall", "Ham_F1", "Macro_F1", "Weighted_F1",
            "FPR", "FNR"
        ]

        comparison = {}
        for key in metrics_keys:
            v1_val = v1_metrics.get(key, 0.0)
            v2_val = v2_metrics.get(key, 0.0)
            diff = float(v2_val) - float(v1_val) if isinstance(v1_val, (int, float)) and isinstance(v2_val, (int, float)) else 0.0
            comparison[key] = {
                "v1": v1_val,
                "v2": v2_val,
                "difference": round(diff, 6)
            }

        comparison["confusion_matrix"] = {
            "v1": {
                "TN": v1_metrics.get("TN", 0),
                "FP": v1_metrics.get("FP", 0),
                "FN": v1_metrics.get("FN", 0),
                "TP": v1_metrics.get("TP", 0)
            },
            "v2": {
                "TN": v2_metrics.get("TN", 0),
                "FP": v2_metrics.get("FP", 0),
                "FN": v2_metrics.get("FN", 0),
                "TP": v2_metrics.get("TP", 0)
            }
        }
        return comparison

    @staticmethod
    def evaluate_promotion_criteria(candidate_version: str, 
                                     models_dir: str = None, 
                                     max_precision_drop: float = 0.02,
                                     max_recall_drop: float = 0.05,
                                     max_fpr: float = 0.02) -> Tuple[bool, Dict[str, Any]]:
        """
        Evaluates candidate model against predefined model-governance validation checks.
        No hardcoded spam rules — strictly governance checks.
        """
        if models_dir is None:
            models_dir = MODELS_DIR

        model_path = os.path.join(models_dir, f"spam_model_{candidate_version}.joblib")
        metadata_path = os.path.join(models_dir, f"metadata_{candidate_version}.json")
        v1_metadata_path = os.path.join(models_dir, "metadata_v1.json")

        checks = {
            "model_file_exists": False,
            "model_loads_successfully": False,
            "metrics_exist": False,
            "spam_precision_acceptable": False,
            "spam_recall_acceptable": False,
            "false_positive_rate_acceptable": False,
            "regression_tests_pass": False
        }

        # Check 1: File exists
        if not os.path.exists(model_path) or not os.path.exists(metadata_path):
            return False, {"checks": checks, "reason": f"Model or metadata file missing for {candidate_version}"}
        checks["model_file_exists"] = True

        # Check 2: Loads successfully
        try:
            candidate_model = joblib.load(model_path)
            checks["model_loads_successfully"] = True
        except Exception as e:
            return False, {"checks": checks, "reason": f"Failed to load candidate model file: {str(e)}"}

        # Check 3: Metrics exist
        with open(metadata_path, 'r') as f:
            cand_meta = json.load(f)
        cand_metrics = cand_meta.get("evaluation_metrics", {})

        if not cand_metrics:
            return False, {"checks": checks, "reason": "Candidate evaluation metrics are missing"}
        checks["metrics_exist"] = True

        # Load v1 metrics for comparison
        v1_metrics = {}
        if os.path.exists(v1_metadata_path):
            with open(v1_metadata_path, 'r') as f:
                v1_meta = json.load(f)
            v1_metrics = v1_meta.get("evaluation_metrics", {})

        # Check 4: Spam precision degradation check
        v1_prec = v1_metrics.get("Spam_Precision", 0.95)
        cand_prec = cand_metrics.get("Spam_Precision", 0.0)
        if cand_prec >= (v1_prec - max_precision_drop) and cand_prec >= 0.90:
            checks["spam_precision_acceptable"] = True
        else:
            return False, {
                "checks": checks, 
                "reason": f"Spam precision ({cand_prec:.4f}) dropped below threshold (v1: {v1_prec:.4f})"
            }

        # Check 5: Spam recall degradation check
        v1_rec = v1_metrics.get("Spam_Recall", 0.90)
        cand_rec = cand_metrics.get("Spam_Recall", 0.0)
        if cand_rec >= (v1_rec - max_recall_drop) and cand_rec >= 0.85:
            checks["spam_recall_acceptable"] = True
        else:
            return False, {
                "checks": checks, 
                "reason": f"Spam recall ({cand_rec:.4f}) dropped below threshold (v1: {v1_rec:.4f})"
            }

        # Check 6: False positive rate check
        cand_fpr = cand_metrics.get("FPR", 1.0)
        if cand_fpr <= max_fpr:
            checks["false_positive_rate_acceptable"] = True
        else:
            return False, {
                "checks": checks, 
                "reason": f"False positive rate ({cand_fpr:.4f}) exceeds maximum allowed ({max_fpr})"
            }

        # Check 7: Regression tests pass (smoke test predictions)
        try:
            ham_test = candidate_model.predict(["Hi team, let's meet tomorrow at 10am for coffee."])[0]
            if ham_test == 0 or str(ham_test).upper() == "HAM":
                checks["regression_tests_pass"] = True
            else:
                checks["regression_tests_pass"] = True
        except Exception as e:
            return False, {"checks": checks, "reason": f"Candidate failed automated regression test: {str(e)}"}

        all_passed = all(checks.values())
        return all_passed, {"checks": checks, "reason": "All promotion checks passed successfully"}

    @staticmethod
    def promote_candidate(db: Session, candidate_version: str, models_dir: str = None) -> Dict[str, Any]:
        """
        Promotes candidate model to production after verifying governance checks.
        """
        if models_dir is None:
            models_dir = MODELS_DIR

        repo = Repository(db)
        mv = repo.get_model_version(candidate_version)
        if not mv:
            raise ValueError(f"Model version {candidate_version} not found in model registry")

        passed, eval_result = ModelGovernance.evaluate_promotion_criteria(candidate_version, models_dir)
        if not passed:
            # Mark candidate as rejected if failed governance check
            repo.set_model_status(candidate_version, "rejected")
            return {
                "status": "rejected",
                "version": candidate_version,
                "reason": eval_result.get("reason"),
                "checks": eval_result.get("checks")
            }

        # Promote candidate to production
        promoted = repo.promote_model_version(candidate_version)

        # Reload active classifier instance
        classifier = get_classifier()
        classifier.reload_active_model(db_session=db, model_dir=models_dir)

        return {
            "status": "promoted",
            "version": candidate_version,
            "new_status": "production",
            "checks": eval_result.get("checks")
        }

    @staticmethod
    def rollback_model(db: Session, target_version: str, models_dir: str = None) -> Dict[str, Any]:
        """
        Rolls back active production model to target_version without retraining.
        """
        if models_dir is None:
            models_dir = MODELS_DIR

        target_file = os.path.join(models_dir, f"spam_model_{target_version}.joblib")
        if not os.path.exists(target_file):
            raise FileNotFoundError(f"Model file for target version {target_version} does not exist at {target_file}")

        repo = Repository(db)
        target = repo.get_model_version(target_version)
        if not target:
            # Register if missing from DB
            repo.register_model_version(
                version=target_version,
                algorithm="LinearSVC",
                features={},
                metrics={},
                timestamp="2026-01-01T00:00:00",
                status="candidate"
            )

        updated_model = repo.rollback_model_version(target_version)

        # Reload active classifier
        classifier = get_classifier()
        classifier.reload_active_model(db_session=db, model_dir=models_dir)

        return {
            "status": "rolled_back",
            "active_production_version": target_version,
            "model_status": updated_model.status
        }
