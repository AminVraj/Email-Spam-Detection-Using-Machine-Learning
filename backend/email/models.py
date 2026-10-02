from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict

@dataclass
class AttachmentMetadata:
    filename: str
    mime_type: str
    size: int

@dataclass
class EmailMessage:
    id: str
    provider: str
    sender: str
    recipients: List[str]
    subject: str
    body: str
    received_at: Optional[datetime] = None
    headers: Dict[str, str] = field(default_factory=dict)
    attachments: List[AttachmentMetadata] = field(default_factory=list)
