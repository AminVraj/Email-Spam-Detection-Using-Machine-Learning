import os
import sys
import json
import joblib
import pandas as pd
from datetime import datetime
from sklearn.pipeline import Pipeline
from sklearn.svm import LinearSVC
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score, confusion_matrix
)

# Ensure project root is on path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.config import MODELS_DIR, TRAINING_DIR, ADAPTIVE_MIN_FEEDBACK
from backend.nlp.pipeline import TextCleaner
from backend.nlp.feature_extraction import build_nlp_features
from backend.ml.feedback_validator import FeedbackValidator
from training.adaptive_dataset import build_combined_dataset, split_training_data_leakproof

def calculate_metrics(y_true, y_pred) -> dict:
    """Calculates comprehensive classification metrics."""
    # Convert string labels to binary if needed: SPAM -> 1, HAM -> 0
    y_true_binary = [1 if str(y).upper() == "SPAM" else 0 for y in y_true]
    y_pred_binary = [1 if str(y).upper() == "SPAM" else 0 for y in y_pred]

    acc = float(accuracy_score(y_true_binary, y_pred_binary))
    tn, fp, fn, tp = confusion_matrix(y_true_binary, y_pred_binary, labels=[0, 1]).ravel()

    spam_prec = float(precision_score(y_true_binary, y_pred_binary, pos_label=1, zero_division=0))
    spam_rec = float(recall_score(y_true_binary, y_pred_binary, pos_label=1, zero_division=0))
    spam_f1 = float(f1_score(y_true_binary, y_pred_binary, pos_label=1, zero_division=0))

    ham_prec = float(precision_score(y_true_binary, y_pred_binary, pos_label=0, zero_division=0))
    ham_rec = float(recall_score(y_true_binary, y_pred_binary, pos_label=0, zero_division=0))
    ham_f1 = float(f1_score(y_true_binary, y_pred_binary, pos_label=0, zero_division=0))

    macro_f1 = float(f1_score(y_true_binary, y_pred_binary, average='macro', zero_division=0))
    weighted_f1 = float(f1_score(y_true_binary, y_pred_binary, average='weighted', zero_division=0))

    fpr = float(fp / (fp + tn)) if (fp + tn) > 0 else 0.0
    fnr = float(fn / (fn + tp)) if (fn + tp) > 0 else 0.0

    return {
        "Accuracy": acc,
        "Spam_Precision": spam_prec,
        "Spam_Recall": spam_rec,
        "Spam_F1": spam_f1,
        "Ham_Precision": ham_prec,
        "Ham_Recall": ham_rec,
        "Ham_F1": ham_f1,
        "Macro_F1": macro_f1,
        "Weighted_F1": weighted_f1,
        "FPR": fpr,
        "FNR": fnr,
        "TN": int(tn),
        "FP": int(fp),
        "FN": int(fn),
        "TP": int(tp)
    }

def build_nlp_pipeline() -> Pipeline:
    """Builds the exact same NLP Pipeline as v1."""
    return Pipeline([
        ('cleaner', TextCleaner()),
        ('features', build_nlp_features()),
        ('classifier', LinearSVC(random_state=42, dual=False))
    ])

def train_candidate_model(db_session, 
                          candidate_version: str = "v2", 
                          models_dir: str = None, 
                          training_dir: str = None,
                          min_feedback_override: int = None) -> dict:
    """
    Executes the controlled adaptive training pipeline for a candidate model.
    1. Validates user feedback.
    2. Checks minimum feedback threshold.
    3. Builds combined training dataset.
    4. Performs leakproof train/test split.
    5. Trains candidate model (SAME NLP architecture as v1).
    6. Evaluates candidate on train and test data.
    7. Saves candidate model and metadata file.
    8. Registers candidate in model_versions table with status = 'candidate'.
    9. Does NOT promote to production.
    """
    if models_dir is None:
        models_dir = MODELS_DIR
    if training_dir is None:
        training_dir = TRAINING_DIR
        
    os.makedirs(models_dir, exist_ok=True)
    os.makedirs(training_dir, exist_ok=True)

    min_required = min_feedback_override if min_feedback_override is not None else ADAPTIVE_MIN_FEEDBACK

    # 1. Validate Feedback
    validator = FeedbackValidator(db_session)
    val_report = validator.validate_all_feedback()
    
    valid_feedback = val_report["valid_feedback"]
    eligible_count = len(valid_feedback)

    # 2. Check Minimum Feedback Threshold
    if eligible_count < min_required:
        return {
            "status": "error",
            "training_ready": False,
            "eligible_feedback": eligible_count,
            "minimum_required": min_required,
            "message": f"Insufficient eligible feedback. {eligible_count} available, {min_required} required."
        }

    # 3. Build Combined Dataset
    combined_df, data_summary = build_combined_dataset(valid_feedback, output_dir=training_dir)

    # 4. Leakproof Train/Test Split
    train_df, test_df = split_training_data_leakproof(combined_df, test_size=0.2, random_state=42)

    X_train, y_train = train_df['text'], train_df['label']
    X_test, y_test = test_df['text'], test_df['label']

    # 5. Train Model Pipeline
    pipeline = build_nlp_pipeline()
    pipeline.fit(X_train, y_train)

    # 6. Evaluate
    y_train_pred = pipeline.predict(X_train)
    y_test_pred = pipeline.predict(X_test)

    train_metrics = calculate_metrics(y_train, y_train_pred)
    test_metrics = calculate_metrics(y_test, y_test_pred)

    # 7. Save Model & Metadata
    model_filename = f"spam_model_{candidate_version}.joblib"
    metadata_filename = f"metadata_{candidate_version}.json"
    
    model_path = os.path.join(models_dir, model_filename)
    metadata_path = os.path.join(models_dir, metadata_filename)

    # Safety check: Ensure v1 is not overwritten
    if candidate_version == "v1" or os.path.abspath(model_path) == os.path.abspath(os.path.join(models_dir, "spam_model_v1.joblib")):
        raise ValueError("Cannot overwrite v1 production model file!")

    joblib.dump(pipeline, model_path)

    metadata = {
        "version": candidate_version,
        "algorithm": "Advanced Linear SVM (Adaptive Candidate)",
        "status": "candidate",
        "feature_configuration": {
            "word_tfidf": "Unigram, Bigram, Trigram (ngram_range=(1,3), min_df=2, max_df=0.95)",
            "char_tfidf": "Character 2-gram to 5-gram (analyzer='char_wb', ngram_range=(2,5), min_df=2, max_df=0.95)"
        },
        "evaluation_metrics": test_metrics,
        "train_metrics": train_metrics,
        "training_timestamp": datetime.now().isoformat(),
        "dataset_information": data_summary,
        "feedback_count_used": eligible_count,
        "parent_model_version": "v1",
        "model_selection_rationale": "Adaptive learning candidate model trained on base dataset + user feedback."
    }

    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=4)

    # 8. Register in Database as candidate
    from backend.database.repository import Repository
    repo = Repository(db_session)
    repo.register_model_version(
        version=candidate_version,
        algorithm="Advanced Linear SVM",
        features=metadata["feature_configuration"],
        metrics=test_metrics,
        timestamp=metadata["training_timestamp"],
        status="candidate",
        training_data_summary=data_summary,
        feedback_count_used=eligible_count,
        parent_model_version="v1"
    )

    return {
        "status": "success",
        "training_ready": True,
        "version": candidate_version,
        "model_status": "candidate",
        "eligible_feedback_used": eligible_count,
        "metrics": test_metrics,
        "train_metrics": train_metrics,
        "model_file": model_path,
        "metadata_file": metadata_path
    }
