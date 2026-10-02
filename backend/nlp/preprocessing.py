import re
import unicodedata

def clean_text(text: str) -> str:
    """
    Cleans and normalizes email text for NLP processing.
    """
    if not isinstance(text, str):
        return ""
    
    # 1. Unicode normalization
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('utf-8', 'ignore')
    
    # 2. Lowercase
    text = text.lower()
    
    # 3. URL normalization
    url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    text = re.sub(url_pattern, ' __url__ ', text)
    
    # 4. Email address normalization
    email_pattern = r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'
    text = re.sub(email_pattern, ' __email__ ', text)
    
    # 5. Number normalization
    number_pattern = r'\b\d+\b'
    text = re.sub(number_pattern, ' __number__ ', text)
    
    # 6. Currency symbols
    currency_pattern = r'[$£€¥]'
    text = re.sub(currency_pattern, ' __currency__ ', text)
    
    # 7. Whitespace normalization
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text
