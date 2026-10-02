from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, Text, Boolean
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime

Base = declarative_base()

class Email(Base):
    __tablename__ = "emails"
    
    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String, nullable=True) # e.g. "gmail", "api"
    provider_message_id = Column(String, nullable=True, index=True)
    sender = Column(String, nullable=True)
    subject = Column(String, nullable=True)
    body_hash = Column(String, nullable=False, index=True)
    # Storing body_text temporarily for feedback loop.
    # PRIVACY NOTE: Email contents are stored for adaptive learning purposes. 
    # Must be secured in production and cleared after retraining.
    body_text = Column(Text, nullable=True) 
    received_at = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    prediction = relationship("Prediction", back_populates="email", uselist=False)
    feedback = relationship("Feedback", back_populates="email")


class Prediction(Base):
    __tablename__ = "predictions"
    
    id = Column(Integer, primary_key=True, index=True)
    email_id = Column(Integer, ForeignKey("emails.id"), nullable=False, unique=True)
    classification = Column(String, nullable=False)
    decision_score = Column(Float, nullable=False)
    model_version = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    email = relationship("Email", back_populates="prediction")


class Feedback(Base):
    __tablename__ = "feedback"
    
    id = Column(Integer, primary_key=True, index=True)
    email_id = Column(Integer, ForeignKey("emails.id"), nullable=False)
    prediction_id = Column(Integer, ForeignKey("predictions.id"), nullable=False)
    original_prediction = Column(String, nullable=False)
    user_label = Column(String, nullable=False)
    model_version = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    email = relationship("Email", back_populates="feedback")


class ModelVersion(Base):
    __tablename__ = "model_versions"
    
    id = Column(Integer, primary_key=True, index=True)
    version = Column(String, nullable=False, unique=True)
    algorithm = Column(String, nullable=False)
    feature_configuration = Column(Text, nullable=False) # Store JSON string
    metrics = Column(Text, nullable=False) # Store JSON string
    training_timestamp = Column(DateTime, nullable=False)
    status = Column(String, nullable=False) # production, candidate, rejected, archived
    training_data_summary = Column(Text, nullable=True) # Store JSON string
    feedback_count_used = Column(Integer, default=0)
    parent_model_version = Column(String, nullable=True)

