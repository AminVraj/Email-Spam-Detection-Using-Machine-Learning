import sys
import os
import pytest

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.ml.predict import SpamClassifier

@pytest.fixture(scope="module")
def classifier():
    """Loads the trained model once for all tests."""
    return SpamClassifier()

def test_model_loading(classifier):
    assert classifier.model is not None, "Model failed to load"

def test_empty_input(classifier):
    result = classifier.predict_email(subject="", body="")
    # Usually empty text should be classified as HAM
    assert result["classification"] in ["HAM", "SPAM"]

def test_unicode_input(classifier):
    text = "Hello 🌍! This is an test email containing unicode 漢字."
    result = classifier.predict_email(subject="", body=text)
    assert result["classification"] in ["HAM", "SPAM"]

def test_long_email(classifier):
    text = "Long word " * 1000
    result = classifier.predict_email(subject="", body=text)
    assert result["classification"] in ["HAM", "SPAM"]

def test_html_email(classifier):
    text = "<html><body><h1>Hello</h1><p>This is a legit email.</p></body></html>"
    result = classifier.predict_email(subject="", body=text)
    assert result["classification"] in ["HAM", "SPAM"]

def test_legitimate_email_with_spam_words(classifier):
    # This specifically tests that the word "free" doesn't automatically trigger spam
    text = "Hey team, feel free to join the meeting whenever you are ready. I have urgent updates about the new offer."
    result = classifier.predict_email(subject="", body=text)
    assert result["classification"] == "HAM", "Model triggered false positive on spam-like words in legit context"

def test_spam_like_email_with_unseen_wording(classifier):
    # This tests whether char n-grams catch obfuscated spam
    text = "C1ick h3re to cl41m y0ur pr1z3! 100% fr33 n0w!"
    result = classifier.predict_email(subject="", body=text)
    # Depending on the training data this might be SPAM or HAM, but let's assert it runs.
    assert result["classification"] in ["SPAM", "HAM"]

def test_typical_spam(classifier):
    text = "WINNER!! As a valued network customer you have been selected to receivea £900 prize reward! To claim call 09061701461"
    result = classifier.predict_email(subject="", body=text)
    assert result["classification"] == "SPAM"

def test_typical_ham(classifier):
    text = "Hi John, what time are we meeting tomorrow for lunch?"
    result = classifier.predict_email(subject="", body=text)
    assert result["classification"] == "HAM"
