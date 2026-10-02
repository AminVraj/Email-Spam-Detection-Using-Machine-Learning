import logging
from sqlalchemy.orm import Session

from backend.email.gmail import GmailProvider
from backend.ml.predict import get_classifier
from backend.database.repository import Repository

logger = logging.getLogger(__name__)

class EmailSyncService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = Repository(db)
        self.provider = GmailProvider()
        self.classifier = get_classifier()

    def sync_recent(self, limit: int = 20) -> dict:
        summary = {
            "fetched": 0,
            "processed": 0,
            "skipped_existing": 0,
            "skipped_invalid": 0,
            "spam": 0,
            "ham": 0,
            "model_version": self.classifier.metadata.get("version", "unknown")
        }

        if not self.provider.authenticate():
            logger.error("Gmail authentication failed.")
            return summary

        emails = self.provider.fetch_emails(limit=limit)
        summary["fetched"] = len(emails)

        for email in emails:
            # Check if exists
            if self.repo.check_email_exists(email.id):
                summary["skipped_existing"] += 1
                continue

            # Validate subject/body
            subject = email.subject.strip() if email.subject else ""
            body = email.body.strip() if email.body else ""

            if not subject and not body:
                summary["skipped_invalid"] += 1
                logger.info(f"Skipped empty email with ID {email.id}")
                continue

            # Classify
            result = self.classifier.predict_email(
                subject=subject,
                body=body,
                sender=email.sender
            )
            classification = result["classification"]
            
            # Store
            self.repo.record_email_and_prediction(
                subject=subject,
                body=body,
                sender=email.sender,
                classification=classification,
                decision_score=result["decision_score"],
                model_version=result["model_version"],
                provider=email.provider,
                provider_message_id=email.id
            )

            summary["processed"] += 1
            if classification == "SPAM":
                summary["spam"] += 1
            else:
                summary["ham"] += 1

        return summary
