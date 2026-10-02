import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from backend.database.models import Base, Email, Prediction, Feedback
from backend.database.repository import Repository

@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture
def repo(db_session):
    return Repository(db_session)

def test_record_email_and_prediction(repo):
    email_id, pred_id = repo.record_email_and_prediction(
        subject="Test", body="Body", sender="test@test.com", 
        classification="HAM", decision_score=0.5, model_version="v1"
    )
    
    email = repo.db.query(Email).filter(Email.id == email_id).first()
    assert email is not None
    assert email.subject == "Test"
    
    pred = repo.db.query(Prediction).filter(Prediction.id == pred_id).first()
    assert pred is not None
    assert pred.classification == "HAM"
    assert pred.email_id == email_id

def test_record_feedback_success(repo):
    email_id, pred_id = repo.record_email_and_prediction(
        subject="Test", body="Body", sender="test@test.com", 
        classification="HAM", decision_score=0.5, model_version="v1"
    )
    
    result = repo.record_feedback(email_id, "SPAM")
    assert result["status"] == "recorded"
    assert result["original_prediction"] == "HAM"
    assert result["user_label"] == "SPAM"
    
    feedback = repo.db.query(Feedback).filter(Feedback.email_id == email_id).first()
    assert feedback is not None
    assert feedback.user_label == "SPAM"

def test_record_feedback_invalid_label(repo):
    email_id, pred_id = repo.record_email_and_prediction(
        subject="Test", body="Body", sender="test@test.com", 
        classification="HAM", decision_score=0.5, model_version="v1"
    )
    
    with pytest.raises(ValueError, match="user_label must be SPAM or HAM"):
        repo.record_feedback(email_id, "INVALID")

def test_record_feedback_duplicate(repo):
    email_id, pred_id = repo.record_email_and_prediction(
        subject="Test", body="Body", sender="test@test.com", 
        classification="HAM", decision_score=0.5, model_version="v1"
    )
    
    repo.record_feedback(email_id, "SPAM")
    
    with pytest.raises(ValueError, match="Feedback already recorded"):
        repo.record_feedback(email_id, "HAM")

def test_get_statistics(repo):
    # Insert 1 HAM prediction
    e1, p1 = repo.record_email_and_prediction(
        subject="1", body="1", sender="1@1", 
        classification="HAM", decision_score=0.5, model_version="v1"
    )
    # Insert 1 SPAM prediction
    e2, p2 = repo.record_email_and_prediction(
        subject="2", body="2", sender="2@2", 
        classification="SPAM", decision_score=0.5, model_version="v1"
    )
    
    # User corrects HAM to SPAM
    repo.record_feedback(e1, "SPAM")
    
    # User confirms SPAM as SPAM
    repo.record_feedback(e2, "SPAM")
    
    stats = repo.get_statistics()
    
    assert stats["total_predictions"] == 2
    assert stats["spam_predictions"] == 1
    assert stats["ham_predictions"] == 1
    assert stats["user_corrections"] == 1
    assert stats["predicted_spam_confirmed_by_user"] == 1
    assert stats["predicted_ham_confirmed_by_user"] == 0
