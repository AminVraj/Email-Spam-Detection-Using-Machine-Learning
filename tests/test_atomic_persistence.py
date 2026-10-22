import os
import sys
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.database.models import Base, Email, Prediction, Feedback
from backend.database.repository import Repository

TEST_DB_URL = "sqlite:///:memory:"

@pytest.fixture
def db_session():
    engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()

def test_successful_atomic_email_prediction_insertion(db_session):
    """Verify that email and prediction are created together atomically."""
    repo = Repository(db_session)
    email_id, pred_id = repo.record_email_and_prediction(
        subject="Atomic Test",
        body="This is an atomic test email.",
        sender="sender@example.com",
        classification="HAM",
        decision_score=0.15,
        model_version="v1",
        account_email="user@gmail.com"
    )

    assert email_id is not None
    assert pred_id is not None

    # Check both records exist in DB
    email = db_session.query(Email).filter(Email.id == email_id).first()
    prediction = db_session.query(Prediction).filter(Prediction.id == pred_id).first()

    assert email is not None
    assert prediction is not None
    assert prediction.email_id == email.id
    assert email.prediction.id == prediction.id

def test_prediction_failure_rolls_back_email_insertion(db_session, monkeypatch):
    """Verify that if prediction creation fails, the email is rolled back and no orphan email exists."""
    repo = Repository(db_session)
    initial_email_count = db_session.query(Email).count()
    initial_pred_count = db_session.query(Prediction).count()

    # Monkeypatch Prediction.__init__ to raise an exception during instantiation
    original_init = Prediction.__init__
    def failing_init(self, *args, **kwargs):
        raise RuntimeError("Simulated failure during Prediction record creation")

    monkeypatch.setattr(Prediction, "__init__", failing_init)

    with pytest.raises(RuntimeError, match="Simulated failure"):
        repo.record_email_and_prediction(
            subject="Will Rollback",
            body="This email must not persist as an orphan.",
            sender="fail@example.com",
            classification="SPAM",
            decision_score=0.99,
            model_version="v1",
            account_email="user@gmail.com"
        )

    # Verify transaction rolled back: email count and prediction count remain unchanged
    final_email_count = db_session.query(Email).count()
    final_pred_count = db_session.query(Prediction).count()

    assert final_email_count == initial_email_count, "Email insert must be rolled back if prediction fails!"
    assert final_pred_count == initial_pred_count

def test_email_insert_failure_leaves_no_prediction(db_session, monkeypatch):
    """Verify that if email insertion fails, no prediction is created."""
    repo = Repository(db_session)
    initial_email_count = db_session.query(Email).count()
    initial_pred_count = db_session.query(Prediction).count()

    original_add = db_session.add
    call_count = [0]
    def failing_add(instance):
        call_count[0] += 1
        if isinstance(instance, Email):
            raise RuntimeError("Simulated failure adding Email to session")
        original_add(instance)

    monkeypatch.setattr(db_session, "add", failing_add)

    with pytest.raises(RuntimeError, match="Simulated failure"):
        repo.record_email_and_prediction(
            subject="Email Add Failure",
            body="This will fail on email add.",
            sender="fail@example.com",
            classification="HAM",
            decision_score=0.1,
            model_version="v1"
        )

    assert db_session.query(Email).count() == initial_email_count
    assert db_session.query(Prediction).count() == initial_pred_count

def test_duplicate_provider_message_does_not_create_duplicates(db_session):
    """Verify that analyzing the same provider message ID reuses the existing email and prediction."""
    repo = Repository(db_session)

    e1_id, p1_id = repo.record_email_and_prediction(
        subject="Provider Msg",
        body="Message body text",
        provider="gmail",
        provider_message_id="msg_duplicate_123",
        classification="HAM",
        decision_score=0.2,
        model_version="v1",
        account_email="alice@gmail.com"
    )

    e2_id, p2_id = repo.record_email_and_prediction(
        subject="Provider Msg Repeated",
        body="Message body text",
        provider="gmail",
        provider_message_id="msg_duplicate_123",
        classification="HAM",
        decision_score=0.2,
        model_version="v1",
        account_email="alice@gmail.com"
    )

    assert e1_id == e2_id
    assert p1_id == p2_id
    assert db_session.query(Email).filter(Email.provider_message_id == "msg_duplicate_123").count() == 1

def test_identical_provider_message_ids_from_different_accounts_isolated(db_session):
    """Verify identical message IDs across different Gmail accounts are persisted separately."""
    repo = Repository(db_session)

    e1_id, p1_id = repo.record_email_and_prediction(
        subject="Account 1 Msg",
        body="Body from account 1",
        provider="gmail",
        provider_message_id="shared_msg_id_999",
        classification="HAM",
        decision_score=0.1,
        model_version="v1",
        account_email="user1@gmail.com"
    )

    e2_id, p2_id = repo.record_email_and_prediction(
        subject="Account 2 Msg",
        body="Body from account 2",
        provider="gmail",
        provider_message_id="shared_msg_id_999",
        classification="SPAM",
        decision_score=0.9,
        model_version="v1",
        account_email="user2@gmail.com"
    )

    assert e1_id != e2_id
    assert p1_id != p2_id

    records = db_session.query(Email).filter(Email.provider_message_id == "shared_msg_id_999").all()
    assert len(records) == 2
    accounts = {r.account_email for r in records}
    assert accounts == {"user1@gmail.com", "user2@gmail.com"}

def test_feedback_relationships_remain_valid(db_session):
    """Verify feedback correctly links to both email and prediction."""
    repo = Repository(db_session)

    e_id, p_id = repo.record_email_and_prediction(
        subject="Feedback Test",
        body="Check feedback linkage",
        classification="SPAM",
        decision_score=0.88,
        model_version="v1",
        account_email="feedback_user@gmail.com"
    )

    fb_result = repo.record_feedback(e_id, "HAM", account_email="feedback_user@gmail.com")
    assert fb_result["status"] == "recorded"

    feedback = db_session.query(Feedback).filter(Feedback.email_id == e_id).first()
    assert feedback is not None
    assert feedback.prediction_id == p_id
    assert feedback.original_prediction == "SPAM"
    assert feedback.user_label == "HAM"
