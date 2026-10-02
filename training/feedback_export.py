import os
import sys
import json
import argparse
from sqlalchemy.orm import Session

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.database.database import SessionLocal
from backend.database.models import Feedback, Email

def export_feedback(output_file="training/feedback_dataset.json"):
    db: Session = SessionLocal()
    
    try:
        # Get all feedback, avoiding duplicates by picking the latest feedback for each email
        # Since we block duplicate feedback at the API level, simple query is fine.
        feedbacks = db.query(Feedback).join(Email).all()
        
        dataset = []
        for fb in feedbacks:
            email = fb.email
            if not email.body_text and not email.subject:
                continue # Skip empty records (shouldn't exist due to API validation)
                
            dataset.append({
                "source": "user_feedback",
                "email_id": email.id,
                "subject": email.subject,
                "body": email.body_text,
                "label": fb.user_label, # "SPAM" or "HAM"
                "original_prediction": fb.original_prediction,
                "model_version": fb.model_version
            })
            
        # Write to JSON
        os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)
        with open(output_file, 'w') as f:
            json.dump(dataset, f, indent=4)
            
        print(f"Successfully exported {len(dataset)} feedback records to {output_file}")
        
    finally:
        db.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export validated feedback for training")
    parser.add_argument("--output", type=str, default="training/feedback_dataset.json", help="Path to output file")
    args = parser.parse_args()
    
    export_feedback(args.output)
