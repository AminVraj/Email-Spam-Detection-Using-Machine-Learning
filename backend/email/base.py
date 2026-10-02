from abc import ABC, abstractmethod
from typing import List, Optional
from backend.email.models import EmailMessage

class EmailProvider(ABC):
    
    @abstractmethod
    def authenticate(self) -> bool:
        """Authenticate with the provider."""
        pass
        
    @abstractmethod
    def fetch_emails(self, limit: int = 20) -> List[EmailMessage]:
        """Fetch a list of recent emails."""
        pass
        
    @abstractmethod
    def get_email(self, message_id: str) -> Optional[EmailMessage]:
        """Get a specific email by its ID."""
        pass
