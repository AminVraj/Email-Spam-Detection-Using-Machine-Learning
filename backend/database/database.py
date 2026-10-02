import os
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from backend.database.models import Base

# Database file location
DB_PATH = os.environ.get("DATABASE_URL", "sqlite:///./spam_detection.db")

engine = create_engine(DB_PATH, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    # Create tables if they do not exist
    Base.metadata.create_all(bind=engine)
    
    # Safe schema migration for SQLite table extensions
    try:
        inspector = inspect(engine)
        if "model_versions" in inspector.get_table_names():
            columns = [c["name"] for c in inspector.get_columns("model_versions")]
            with engine.connect() as conn:
                if "training_data_summary" not in columns:
                    conn.execute(text("ALTER TABLE model_versions ADD COLUMN training_data_summary TEXT"))
                if "feedback_count_used" not in columns:
                    conn.execute(text("ALTER TABLE model_versions ADD COLUMN feedback_count_used INTEGER DEFAULT 0"))
                if "parent_model_version" not in columns:
                    conn.execute(text("ALTER TABLE model_versions ADD COLUMN parent_model_version TEXT"))
                conn.commit()
    except Exception:
        pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
