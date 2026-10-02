import os
from unittest.mock import patch

def test_load_dotenv_works():
    # We mock the .env file loading by putting fake variables in env
    with patch.dict(os.environ, {"GMAIL_EMAIL": "configtest@gmail.com", "GMAIL_APP_PASSWORD": "configpass"}):
        from backend.email.gmail import GmailProvider
        provider = GmailProvider()
        
        # Test that they load correctly
        assert provider.email == "configtest@gmail.com"
        assert provider.password == "configpass"

def test_credentials_are_not_hardcoded():
    # Ensure they are fetched from os.environ and are not hardcoded values when env is empty
    with patch.dict(os.environ, {}, clear=True):
        from backend.email.gmail import GmailProvider
        provider = GmailProvider()
        assert provider.email is None
        assert provider.password is None
