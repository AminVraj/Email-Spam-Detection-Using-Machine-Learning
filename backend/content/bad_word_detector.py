import re
from typing import List, Tuple

from backend.content.bad_words import BAD_WORDS_LIST

class BadWordDetector:
    def __init__(self, custom_words: List[str] = None):
        self.words = set([w.lower() for w in (custom_words or BAD_WORDS_LIST)])

    def check_text(self, text: str) -> Tuple[bool, int]:
        """
        Checks normalized text for bad words.
        Returns a tuple: (is_blocked, number_of_bad_words_detected)
        """
        if not text:
            return False, 0

        # Basic normalization for bad word checking
        text = text.lower()
        # Find all words
        words = re.findall(r'\b\w+\b', text)

        detected_count = sum(1 for word in words if word in self.words)

        return detected_count > 0, detected_count
