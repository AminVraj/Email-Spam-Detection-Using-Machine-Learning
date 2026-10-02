import os
import sys
import json
import joblib
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.database.models import Base, Email, Prediction, Feedback, ModelVersion
from backend.database.repository import Repository
from backend.ml.feedback_validator import FeedbackValidator
from backend.ml.model_governance import ModelGovernance
from backend.ml.predict import SpamClassifier
from training.adaptive_dataset import build_combined_dataset, split_training_data_leakproof, load_base_dataset
from training.train_adaptive import train_candidate_model, calculate_metrics, build_nlp_pipeline

REAL_V1_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "models", "spam_model_v1.joblib"))

@pytest.fixture
def test_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    # Initialize v1 production model in DB
    repo = Repository(db)
    repo.register_model_version(
        version="v1",
        algorithm="Advanced Linear SVM",
        features={"word": "tfidf", "char": "tfidf"},
        metrics={"Accuracy": 0.99, "Spam_Precision": 1.0, "Spam_Recall": 0.93, "Spam_F1": 0.96, "FPR": 0.0},
        timestamp="2026-09-30T10:00:00",
        status="production"
    )
    try:
        yield db
    finally:
        db.close()

@pytest.fixture
def repo(test_db):
    return Repository(test_db)

# Test 1: Valid feedback
def test_valid_feedback_validation(test_db, repo):
    e1, p1 = repo.record_email_and_prediction("Project Update", "Hey team, project is on schedule.", "dev@test.com", "HAM", 0.8, "v1")
    repo.record_feedback(e1, "HAM")
    
    validator = FeedbackValidator(test_db)
    report = validator.validate_all_feedback()
    
    assert report["valid_count"] == 1
    assert report["invalid_count"] == 0
    assert report["valid_feedback"][0]["email_id"] == e1
    assert report["valid_feedback"][0]["label"] == "HAM"

# Test 2: Invalid feedback label
def test_invalid_feedback_label(repo):
    e1, p1 = repo.record_email_and_prediction("Test", "Body text", "sender@test.com", "HAM", 0.5, "v1")
    with pytest.raises(ValueError, match="user_label must be SPAM or HAM"):
        repo.record_feedback(e1, "INVALID_LABEL")

# Test 3: Duplicate feedback
def test_duplicate_feedback(repo):
    e1, p1 = repo.record_email_and_prediction("Test", "Body text", "sender@test.com", "HAM", 0.5, "v1")
    repo.record_feedback(e1, "HAM")
    with pytest.raises(ValueError, match="Feedback already recorded"):
        repo.record_feedback(e1, "SPAM")

# Test 4: Conflicting feedback detection
def test_conflicting_feedback(test_db, repo):
    e1, p1 = repo.record_email_and_prediction("Identical Subject", "Identical Body Content Here", "s1@test.com", "HAM", 0.5, "v1")
    e2, p2 = repo.record_email_and_prediction("Identical Subject", "Identical Body Content Here", "s2@test.com", "HAM", 0.5, "v1")
    
    repo.record_feedback(e1, "SPAM")
    repo.record_feedback(e2, "HAM")
    
    validator = FeedbackValidator(test_db)
    report = validator.validate_all_feedback()
    
    assert report["conflicting_count"] >= 1
    assert report["valid_count"] == 0

# Test 5: Empty email feedback
def test_empty_email_feedback(test_db, repo):
    email = Email(subject="", body_text="", body_hash="empty")
    test_db.add(email)
    test_db.commit()
    test_db.refresh(email)
    
    pred = Prediction(email_id=email.id, classification="HAM", decision_score=0.1, model_version="v1")
    test_db.add(pred)
    test_db.commit()
    test_db.refresh(pred)
    
    fb = Feedback(email_id=email.id, prediction_id=pred.id, original_prediction="HAM", user_label="HAM", model_version="v1")
    test_db.add(fb)
    test_db.commit()
    
    validator = FeedbackValidator(test_db)
    report = validator.validate_all_feedback()
    assert any("empty" in inv["reason"].lower() for inv in report["invalid_feedback"])

# Test 6: Feedback linked to missing email
def test_feedback_missing_email(test_db):
    fb = Feedback(email_id=99999, prediction_id=88888, original_prediction="HAM", user_label="HAM", model_version="v1")
    test_db.add(fb)
    test_db.commit()
    
    validator = FeedbackValidator(test_db)
    report = validator.validate_all_feedback()
    assert any("not found" in inv["reason"].lower() for inv in report["invalid_feedback"])

# Test 7: Minimum feedback not reached
def test_min_feedback_not_reached(test_db, repo):
    e1, p1 = repo.record_email_and_prediction("Valid Email", "Valid email text for testing minimum threshold", "s@test.com", "HAM", 0.9, "v1")
    repo.record_feedback(e1, "HAM")
    
    result = train_candidate_model(test_db, candidate_version="v2", min_feedback_override=5)
    assert result["status"] == "error"
    assert result["training_ready"] is False
    assert result["eligible_feedback"] == 1
    assert result["minimum_required"] == 5

# Test 8: Minimum feedback reached
def test_min_feedback_reached(test_db, repo, tmp_path):
    for i in range(2):
        e, p = repo.record_email_and_prediction(f"Subj {i}", f"Unique email body content number {i}", f"s{i}@test.com", "HAM", 0.9, "v1")
        repo.record_feedback(e, "HAM")
        
    models_dir = os.path.join(tmp_path, "models")
    training_dir = os.path.join(tmp_path, "training")
    
    result = train_candidate_model(test_db, candidate_version="v2", models_dir=models_dir, training_dir=training_dir, min_feedback_override=2)
    assert result["status"] == "success"
    assert result["training_ready"] is True
    assert result["model_status"] == "candidate"

# Test 9: Combined dataset creation
def test_combined_dataset_creation(tmp_path):
    val_feedback = [
        {"text": "User feedback email 1", "label": "SPAM", "email_id": 101, "model_version": "v1"},
        {"text": "User feedback email 2", "label": "HAM", "email_id": 102, "model_version": "v1"}
    ]
    
    training_dir = os.path.join(tmp_path, "training")
    combined_df, summary = build_combined_dataset(val_feedback, output_dir=training_dir)
    
    assert summary["user_feedback_records"] == 2
    assert "user_feedback" in combined_df['source'].values
    assert "original_dataset" in combined_df['source'].values

# Test 10: Duplicate prevention between train/test (data leakage prevention)
def test_data_leakage_prevention(tmp_path):
    val_feedback = [
        {"text": "Same repeated string content", "label": "HAM", "email_id": 1, "model_version": "v1"},
        {"text": "Same repeated string content", "label": "HAM", "email_id": 2, "model_version": "v1"},
        {"text": "Different content email text 1", "label": "SPAM", "email_id": 3, "model_version": "v1"},
        {"text": "Different content email text 2", "label": "HAM", "email_id": 4, "model_version": "v1"}
    ]
    training_dir = os.path.join(tmp_path, "training")
    combined_df, _ = build_combined_dataset(val_feedback, output_dir=training_dir)
    
    train_df, test_df = split_training_data_leakproof(combined_df, test_size=0.2, random_state=42)
    
    train_texts = set(train_df['text'])
    test_texts = set(test_df['text'])
    
    assert train_texts.isdisjoint(test_texts), "Data leakage: text overlap found between train and test sets!"

# Test 11: Candidate training execution
def test_candidate_training(test_db, repo, tmp_path):
    for i in range(2):
        e, p = repo.record_email_and_prediction(f"Email {i}", f"Detailed email content body {i}", f"s{i}@t.com", "HAM", 0.5, "v1")
        repo.record_feedback(e, "HAM")
        
    models_dir = os.path.join(tmp_path, "models")
    training_dir = os.path.join(tmp_path, "training")
    
    res = train_candidate_model(test_db, candidate_version="v2", models_dir=models_dir, training_dir=training_dir, min_feedback_override=2)
    assert res["status"] == "success"
    assert os.path.exists(res["model_file"])
    assert os.path.exists(res["metadata_file"])

# Test 12: Candidate model loading
def test_candidate_model_loading(test_db, repo, tmp_path):
    for i in range(2):
        e, p = repo.record_email_and_prediction(f"Title {i}", f"Text message content body {i}", f"s{i}@t.com", "HAM", 0.5, "v1")
        repo.record_feedback(e, "HAM")
        
    models_dir = os.path.join(tmp_path, "models")
    training_dir = os.path.join(tmp_path, "training")
    
    train_candidate_model(test_db, candidate_version="v2", models_dir=models_dir, training_dir=training_dir, min_feedback_override=2)
    
    candidate_model_path = os.path.join(models_dir, "spam_model_v2.joblib")
    loaded_model = joblib.load(candidate_model_path)
    assert loaded_model is not None
    pred = loaded_model.predict(["Hello world test"])[0]
    assert pred in [0, 1, "HAM", "SPAM"]

# Test 13: Metric generation
def test_metric_generation():
    y_true = ["HAM", "SPAM", "HAM", "SPAM", "HAM"]
    y_pred = ["HAM", "SPAM", "HAM", "HAM", "HAM"]
    
    metrics = calculate_metrics(y_true, y_pred)
    assert "Accuracy" in metrics
    assert "Spam_Precision" in metrics
    assert "Spam_Recall" in metrics
    assert "Spam_F1" in metrics
    assert "Ham_Precision" in metrics
    assert "Ham_Recall" in metrics
    assert "FPR" in metrics
    assert "FNR" in metrics
    assert "TN" in metrics
    assert "FP" in metrics
    assert "FN" in metrics
    assert "TP" in metrics

# Test 14: Model comparison
def test_model_comparison():
    v1_metrics = {"Accuracy": 0.99, "Spam_Precision": 1.0, "Spam_Recall": 0.93, "Spam_F1": 0.96, "FPR": 0.0, "TN": 90, "FP": 0, "FN": 7, "TP": 93}
    v2_metrics = {"Accuracy": 0.995, "Spam_Precision": 1.0, "Spam_Recall": 0.96, "Spam_F1": 0.98, "FPR": 0.0, "TN": 90, "FP": 0, "FN": 4, "TP": 96}
    
    comp = ModelGovernance.compare_models(v1_metrics, v2_metrics)
    assert "Accuracy" in comp
    assert comp["Accuracy"]["v1"] == 0.99
    assert comp["Accuracy"]["v2"] == 0.995
    assert comp["Accuracy"]["difference"] == 0.005

# Test 15: Candidate registration
def test_candidate_registration(test_db, repo):
    mv = repo.register_model_version(
        version="v2",
        algorithm="LinearSVC",
        features={"feat": "tfidf"},
        metrics={"Accuracy": 0.99},
        timestamp="2026-09-30T12:00:00",
        status="candidate",
        feedback_count_used=10
    )
    assert mv.version == "v2"
    assert mv.status == "candidate"
    assert mv.feedback_count_used == 10

# Test 16: Explicit promotion
def test_explicit_promotion(test_db, repo, tmp_path):
    models_dir = os.path.join(tmp_path, "models")
    os.makedirs(models_dir, exist_ok=True)
    
    for i in range(2):
        e, p = repo.record_email_and_prediction(f"Email {i}", f"Email content text {i}", f"s{i}@t.com", "HAM", 0.5, "v1")
        repo.record_feedback(e, "HAM")
        
    train_candidate_model(test_db, candidate_version="v2", models_dir=models_dir, training_dir=os.path.join(tmp_path, "training"), min_feedback_override=2)
    
    with open(os.path.join(models_dir, "metadata_v1.json"), 'w') as f:
        json.dump({"evaluation_metrics": {"Spam_Precision": 1.0, "Spam_Recall": 0.9, "FPR": 0.0}}, f)
        
    res = ModelGovernance.promote_candidate(test_db, candidate_version="v2", models_dir=models_dir)
    assert res["status"] == "promoted"
    assert res["new_status"] == "production"
    
    v2_record = repo.get_model_version("v2")
    assert v2_record.status == "production"
    
    v1_record = repo.get_model_version("v1")
    assert v1_record.status == "archived"

# Test 17: Production model selection
def test_production_model_selection(test_db, repo):
    active = repo.get_active_production_model()
    assert active is not None
    assert active.version == "v1"
    assert active.status == "production"

# Test 18: Rollback workflow
def test_rollback_workflow(test_db, repo, tmp_path):
    models_dir = os.path.join(tmp_path, "models")
    os.makedirs(models_dir, exist_ok=True)
    
    real_v1_model = joblib.load(REAL_V1_PATH)
    joblib.dump(real_v1_model, os.path.join(models_dir, "spam_model_v1.joblib"))
    joblib.dump(real_v1_model, os.path.join(models_dir, "spam_model_v2.joblib"))
    
    repo.register_model_version("v2", "LinearSVC", {}, {}, "2026-09-30T12:00:00", status="candidate")
    
    # 1. Promote v2
    repo.promote_model_version("v2")
    assert repo.get_active_production_model().version == "v2"
    
    # 2. Rollback to v1
    rollback_res = ModelGovernance.rollback_model(test_db, target_version="v1", models_dir=models_dir)
    assert rollback_res["status"] == "rolled_back"
    assert rollback_res["active_production_version"] == "v1"
    assert repo.get_active_production_model().version == "v1"

# Test 19: Single production model constraint
def test_single_production_model_constraint(test_db, repo):
    repo.register_model_version("v2", "LinearSVC", {}, {}, "2026-09-30T12:00:00", status="candidate")
    repo.promote_model_version("v2")
    
    prods = test_db.query(ModelVersion).filter(ModelVersion.status == "production").all()
    assert len(prods) == 1
    assert prods[0].version == "v2"

# Test 20: v1 remains intact and available
def test_v1_remains_intact_and_available(test_db, repo):
    assert os.path.exists(REAL_V1_PATH), "v1 model file must exist in production models directory!"

# Test 21: Failed candidate does not replace production
def test_failed_candidate_rejection(test_db, repo, tmp_path):
    models_dir = os.path.join(tmp_path, "models")
    os.makedirs(models_dir, exist_ok=True)
    
    real_v1_model = joblib.load(REAL_V1_PATH)
    joblib.dump(real_v1_model, os.path.join(models_dir, "spam_model_v2.joblib"))
    
    cand_meta = {
        "evaluation_metrics": {
            "Spam_Precision": 0.50, # Unacceptable precision drop
            "Spam_Recall": 0.50,
            "FPR": 0.50
        }
    }
    with open(os.path.join(models_dir, "metadata_v2.json"), 'w') as f:
        json.dump(cand_meta, f)
        
    repo.register_model_version("v2", "LinearSVC", {}, cand_meta["evaluation_metrics"], "2026-09-30T12:00:00", status="candidate")
    
    res = ModelGovernance.promote_candidate(test_db, candidate_version="v2", models_dir=models_dir)
    assert res["status"] == "rejected"
    assert repo.get_active_production_model().version == "v1"

# Test 22: Inference uses production model only
def test_inference_production_only(test_db, repo):
    classifier = SpamClassifier(active_version="v1")
    res = classifier.predict_email("Subject", "Body content")
    assert res["model_version"] == "v1"

# Test 23: Observed false positive tracking
def test_false_positive_tracking(repo):
    e, p = repo.record_email_and_prediction("Meeting", "Team sync at 2pm", "boss@work.com", "SPAM", 1.5, "v1")
    repo.record_feedback(e, "HAM")
    
    stats = repo.get_statistics()
    outcomes = stats["user_feedback_observed_outcomes"]
    assert outcomes["false_positives"] == 1
    assert outcomes["description"] == "User-feedback-based observed outcomes"

# Test 24: Observed false negative tracking
def test_false_negative_tracking(repo):
    e, p = repo.record_email_and_prediction("Winner", "Claim your free cash prize!", "scammer@spam.com", "HAM", -0.5, "v1")
    repo.record_feedback(e, "SPAM")
    
    stats = repo.get_statistics()
    outcomes = stats["user_feedback_observed_outcomes"]
    assert outcomes["false_negatives"] == 1
