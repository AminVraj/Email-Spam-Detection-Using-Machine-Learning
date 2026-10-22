import os
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import List, Optional
from imapclient import IMAPClient
import pyzmail

from backend.email.base import EmailProvider
from backend.email.models import EmailMessage, AttachmentMetadata
from backend.email.normalizer import normalize_email_body

class GmailProvider(EmailProvider):
    def __init__(self):
        self.email = os.environ.get("GMAIL_EMAIL")
        self.password = os.environ.get("GMAIL_APP_PASSWORD")
        self.server = None

    def authenticate(self) -> bool:
        if not self.email or not self.password:
            return False
        try:
            self.server = IMAPClient("imap.gmail.com")
            self.server.login(self.email, self.password)
            return True
        except Exception:
            return False

    def _parse_message(self, uid, raw_msg, category="PRIMARY") -> EmailMessage:
        msg = pyzmail.PyzMessage.factory(raw_msg)

        # Sender
        sender = ""
        addresses = msg.get_addresses("from")
        if addresses:
            sender = addresses[0][1]

        # Recipients
        recipients = []
        for to in msg.get_addresses("to"):
            recipients.append(to[1])

        # Subject
        subject = msg.get_subject() or ""

        # Body
        body = ""
        if msg.text_part:
            try:
                body_bytes = msg.text_part.get_payload()
                if isinstance(body_bytes, bytes):
                    charset = msg.text_part.charset or "utf-8"
                    raw_text = body_bytes.decode(charset, errors="replace")
                    body = normalize_email_body(raw_text, is_html=False)
            except Exception:
                pass

        if not body and msg.html_part:
            try:
                body_bytes = msg.html_part.get_payload()
                if isinstance(body_bytes, bytes):
                    charset = msg.html_part.charset or "utf-8"
                    raw_html = body_bytes.decode(charset, errors="replace")
                    body = normalize_email_body(raw_html, is_html=True)
            except Exception:
                pass

        # Headers
        headers = {}
        for header in ["From", "To", "Subject", "Date", "Reply-To", "Message-ID"]:
            val = msg.get_decoded_header(header)
            if val:
                headers[header] = val

        # Message ID (fallback to IMAP UID)
        message_id = headers.get("Message-ID", str(uid))

        # Received at
        received_at = None
        date_header = headers.get("Date")
        if date_header:
            try:
                received_at = parsedate_to_datetime(date_header)
                if received_at.tzinfo is not None:
                    received_at = received_at.replace(tzinfo=None) # naive UTC
            except Exception:
                pass

        # Attachments metadata
        attachments = []
        for part in msg.mailparts:
            if part.filename:
                filename = part.filename
                mime_type = part.type
                size = len(part.get_payload()) if part.get_payload() else 0
                attachments.append(AttachmentMetadata(filename=filename, mime_type=mime_type, size=size))

        return EmailMessage(
            id=message_id,
            provider="gmail",
            provider_category=category,
            sender=sender,
            recipients=recipients,
            subject=subject,
            body=body,
            received_at=received_at,
            headers=headers,
            attachments=attachments
        )

    def fetch_emails(self, limit: int = 20) -> List[EmailMessage]:
        if not self.server:
            if not self.authenticate():
                return []

        try:
            self.server.select_folder("INBOX")

            # Fetch Primary and Promotions
            primary_uids = self.server.gmail_search("is:unread category:primary")
            promo_uids = self.server.gmail_search("is:unread category:promotions")

            # Map UIDs to categories
            uid_categories = {}
            for uid in primary_uids:
                uid_categories[uid] = "PRIMARY"
            for uid in promo_uids:
                uid_categories[uid] = "PROMOTIONS"

            all_uids = list(uid_categories.keys())

            if not all_uids:
                return []

            all_uids = all_uids[:limit]

            raw_data = self.server.fetch(all_uids, ["BODY.PEEK[]"])

            parsed_emails = []
            for uid, data in raw_data.items():
                raw_msg = data.get(b"BODY[]") or data.get(b"BODY.PEEK[]")
                if not raw_msg:
                    continue

                category = uid_categories.get(uid, "PRIMARY")
                parsed_email = self._parse_message(uid, raw_msg, category=category)

                # Mark as seen
                self.server.add_flags(uid, ["\\Seen"])

                parsed_emails.append(parsed_email)

            return parsed_emails

        except Exception as e:
            return []

    def get_email(self, message_id: str) -> Optional[EmailMessage]:
        return None
