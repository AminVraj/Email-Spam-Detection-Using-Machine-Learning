import re

from spellchecker import SpellChecker
from nltk.stem import WordNetLemmatizer


# ============================================================
# COMPLAINTIQ AI
# LOCAL NLP + RULE FILTER
# VERSION 4
# ============================================================


# ============================================================
# INITIALIZE NLP TOOLS
# ============================================================

spell = SpellChecker(
    distance=2
)

lemmatizer = WordNetLemmatizer()


# ============================================================
# DOMAIN-SPECIFIC WORDS
# ============================================================
#
# These words should NOT be "corrected" by the spell checker.
#
# Example:
# internet
# wifi
# refund
# complaint
# delivery
# billing
#
# ============================================================

DOMAIN_WORDS = {
    "complaint",
    "complaints",
    "complain",
    "complained",

    "internet",
    "wifi",
    "network",
    "connection",

    "billing",
    "bill",
    "charged",
    "charge",

    "refund",
    "refunds",

    "delivery",
    "delivered",

    "product",
    "products",

    "service",
    "services",

    "customer",
    "customers",

    "support",

    "account",
    "accounts",

    "payment",
    "payments",

    "transaction",
    "transactions",

    "damaged",
    "damage",

    "defective",

    "replacement",
    "replace",

    "subscription",
    "subscriptions",

    "order",
    "orders",

    "shipping",
    "shipment",

    "cancel",
    "cancelled",
    "cancellation",

    "password",
    "login",
    "authentication",

    "website",
    "application",
    "app",
}


# Add domain words to spell checker's vocabulary

spell.word_frequency.load_words(
    DOMAIN_WORDS
)


# ============================================================
# MANUAL HIGH-VALUE CORRECTIONS
# ============================================================
#
# These are common mistakes that are particularly important
# for complaint detection.
#
# ============================================================

COMMON_CORRECTIONS = {

    "comlaint": "complaint",
    "complant": "complaint",
    "complait": "complaint",
    "complaintt": "complaint",

    "complanit": "complaint",
    "compliaint": "complaint",

    "proble": "problem",
    "problm": "problem",
    "probem": "problem",

    "isssue": "issue",
    "isue": "issue",

    "recieve": "receive",
    "recived": "received",
    "receved": "received",

    "delivary": "delivery",
    "delivaryy": "delivery",
    "delievery": "delivery",

    "damged": "damaged",
    "dammaged": "damaged",

    "defectve": "defective",

    "refnd": "refund",
    "refud": "refund",

    "chargd": "charged",
    "chared": "charged",

    "paymnt": "payment",
    "pament": "payment",

    "servce": "service",
    "serivce": "service",

    "suppport": "support",
    "suport": "support",

    "internt": "internet",
    "intenet": "internet",

    "conection": "connection",
    "connnection": "connection",

    "netwrk": "network",

    "wrogn": "wrong",
    "wrng": "wrong",

    "incorect": "incorrect",
    "incorrct": "incorrect",

    "missng": "missing",

    "faild": "failed",
    "faield": "failed",

    "unabel": "unable",

    "disapointed": "disappointed",
    "disappointd": "disappointed",

    "unhapy": "unhappy",

    "terribl": "terrible",

    "urgnt": "urgent",
}


# ============================================================
# IGNORED SENDERS
# ============================================================

IGNORED_SENDER_PREFIXES = {

    "noreply",
    "no-reply",
    "donotreply",
    "do-not-reply",

    "notifications",
    "notification",

    "newsletter",

    "marketing",

    "mailer",

    "updates",

    "alert",
}


# ============================================================
# IGNORED DOMAINS
# ============================================================

IGNORED_DOMAINS = {

    "linkedin.com",
    "github.com",
    "instagram.com",
    "spotify.com",
    "evernote.com",
}


# ============================================================
# PROMOTIONAL SUBJECT KEYWORDS
# ============================================================

PROMOTIONAL_SUBJECT_KEYWORDS = {

    "discount",
    "sale",
    "offer",
    "special offer",

    "limited time",
    "deal",

    "promotion",
    "promotional",

    "free",
    "save",

    "cashback",
    "coupon",

    "subscribe",
    "subscription",

    "premium",
    "upgrade",
    "unlock",

    "new features",

    "newsletter",

    "webinar",
    "event",
}


# ============================================================
# PROMOTIONAL BODY KEYWORDS
# ============================================================

PROMOTIONAL_BODY_KEYWORDS = {

    "unsubscribe",
    "view in browser",
    "manage preferences",

    "marketing email",
    "promotional email",

    "limited time offer",
    "special offer",

    "buy now",
    "shop now",

    "learn more",
    "click here",

    "get started",
}


# ============================================================
# COMPLAINT KEYWORDS
# ============================================================

STRONG_COMPLAINT_KEYWORDS = {

    "complaint",
    "complain",

    "problem",
    "issue",

    "broken",
    "wrong",
    "incorrect",

    "damaged",
    "defective",

    "refund",
    "charged",
    "charge",

    "wrong charge",
    "double charged",
    "overcharged",

    "failed",
    "failure",

    "unable",
    "cannot",
    "can't",

    "missing",
    "lost",

    "fraud",
    "scam",

    "disappointed",
    "unhappy",
    "terrible",

    "poor service",
    "bad service",

    "not working",
    "doesn't work",
    "does not work",

    "stopped working",
    "not responding",

    "late",
    "delayed",
    "delay",

    "never received",
    "not received",

    "wrong product",
    "wrong item",

    "damaged product",
    "damaged item",
}


# ============================================================
# CUSTOMER SUPPORT PHRASES
# ============================================================

CUSTOMER_SUPPORT_PHRASES = {

    "please resolve",
    "please fix",
    "please help",

    "need help",
    "need assistance",

    "looking for a solution",

    "resolve this",
    "fix this",

    "take action",

    "contact support",
    "contact customer support",

    "waiting for",
    "still waiting",

    "please look into",
    "look into this",

    "need this resolved",
}


# ============================================================
# NORMAL EMAIL KEYWORDS
# ============================================================

NORMAL_EMAIL_KEYWORDS = {

    "greetings",
    "hello",
    "hi",

    "good morning",
    "good afternoon",
    "good evening",

    "thank you",
    "thanks",

    "congratulations",
    "congrats",

    "meeting",
    "invitation",

    "job",
    "resume",
    "interview",
    "application",

    "information",
    "question",
}


# ============================================================
# TEXT NORMALIZATION
# ============================================================

def normalize_text(text):

    if not text:
        return ""

    text = str(text)

    # Lowercase

    text = text.lower()

    # Remove URLs

    text = re.sub(
        r"https?://\S+|www\.\S+",
        " ",
        text
    )

    # Remove email addresses

    text = re.sub(
        r"\S+@\S+",
        " ",
        text
    )

    # Replace non-letter characters with spaces

    text = re.sub(
        r"[^a-zA-Z\s]",
        " ",
        text
    )

    # Remove extra spaces

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


# ============================================================
# TOKENIZATION
# ============================================================

def tokenize(text):

    return re.findall(
        r"[a-zA-Z]+",
        text.lower()
    )


# ============================================================
# SPELL CORRECTION
# ============================================================

def correct_spelling(word):

    word = word.lower()

    # --------------------------------------------------------
    # Don't correct very short words
    # --------------------------------------------------------

    if len(word) <= 2:

        return word

    # --------------------------------------------------------
    # Domain-specific vocabulary
    # --------------------------------------------------------

    if word in DOMAIN_WORDS:

        return word

    # --------------------------------------------------------
    # Manual corrections
    # --------------------------------------------------------

    if word in COMMON_CORRECTIONS:

        return COMMON_CORRECTIONS[word]

    # --------------------------------------------------------
    # Already known to spell checker
    # --------------------------------------------------------

    if word in spell:

        return word

    # --------------------------------------------------------
    # Ask pyspellchecker for correction
    # --------------------------------------------------------

    correction = spell.correction(
        word
    )

    if not correction:

        return word

    return correction


# ============================================================
# SPELL-CORRECT TEXT
# ============================================================

def spell_correct_text(text):

    tokens = tokenize(text)

    corrected_tokens = []

    corrections = []

    for word in tokens:

        corrected = correct_spelling(
            word
        )

        corrected_tokens.append(
            corrected
        )

        if corrected != word:

            corrections.append(
                f"{word} -> {corrected}"
            )

    return (
        " ".join(corrected_tokens),
        corrections
    )


# ============================================================
# LEMMATIZATION
# ============================================================

def lemmatize_text(text):

    tokens = tokenize(text)

    lemmas = []

    for word in tokens:

        # Try noun form

        lemma = lemmatizer.lemmatize(
            word
        )

        # Try verb form

        lemma = lemmatizer.lemmatize(
            lemma,
            pos="v"
        )

        lemmas.append(
            lemma
        )

    return " ".join(lemmas)


# ============================================================
# COMPLETE NLP PIPELINE
# ============================================================

def preprocess_text(text):

    # --------------------------------------------------------
    # Step 1 - Cleaning
    # --------------------------------------------------------

    cleaned = normalize_text(
        text
    )

    # --------------------------------------------------------
    # Step 2 - Spell correction
    # --------------------------------------------------------

    corrected, corrections = (
        spell_correct_text(
            cleaned
        )
    )

    # --------------------------------------------------------
    # Step 3 - Lemmatization
    # --------------------------------------------------------

    lemmatized = lemmatize_text(
        corrected
    )

    return {
        "cleaned": cleaned,
        "corrected": corrected,
        "lemmatized": lemmatized,
        "corrections": corrections,
    }


# ============================================================
# SENDER HELPERS
# ============================================================

def extract_domain(sender):

    if "@" not in sender:

        return ""

    return sender.lower().split(
        "@"
    )[-1].strip()


def extract_username(sender):

    if "@" not in sender:

        return ""

    return sender.lower().split(
        "@"
    )[0].strip()


# ============================================================
# SENDER CHECK
# ============================================================

def is_ignored_sender(sender):

    sender = sender.lower().strip()

    username = extract_username(
        sender
    )

    domain = extract_domain(
        sender
    )

    # Known domain

    if domain in IGNORED_DOMAINS:

        return True

    # Automated sender

    for prefix in IGNORED_SENDER_PREFIXES:

        if username.startswith(prefix):

            return True

    return False


# ============================================================
# PROMOTION SCORE
# ============================================================

def calculate_promotion_score(
    subject,
    body
):

    subject = normalize_text(
        subject
    )

    body = normalize_text(
        body
    )

    score = 0

    signals = []

    # --------------------------------------------------------
    # Subject
    # --------------------------------------------------------

    for keyword in PROMOTIONAL_SUBJECT_KEYWORDS:

        if keyword in subject:

            score += 2

            signals.append(
                f"promotional subject: {keyword}"
            )

    # --------------------------------------------------------
    # Body
    # --------------------------------------------------------

    for keyword in PROMOTIONAL_BODY_KEYWORDS:

        if keyword in body:

            score += 1

            signals.append(
                f"promotional body: {keyword}"
            )

    return score, signals


# ============================================================
# COMPLAINT SCORE
# ============================================================

def calculate_complaint_score(
    subject,
    body
):

    # --------------------------------------------------------
    # Combine subject + body
    # --------------------------------------------------------

    combined = (
        subject
        + " "
        + body
    )

    # --------------------------------------------------------
    # Run NLP pipeline
    # --------------------------------------------------------

    nlp = preprocess_text(
        combined
    )

    corrected_text = nlp[
        "corrected"
    ]

    lemmatized_text = nlp[
        "lemmatized"
    ]

    # Use both forms

    text = (
        corrected_text
        + " "
        + lemmatized_text
    )

    score = 0

    matched_keywords = []

    # --------------------------------------------------------
    # Complaint keywords
    # --------------------------------------------------------

    for keyword in STRONG_COMPLAINT_KEYWORDS:

        keyword_clean = normalize_text(
            keyword
        )

        # Exact phrase

        if keyword_clean in text:

            score += 3

            matched_keywords.append(
                keyword
            )

    # --------------------------------------------------------
    # Support phrases
    # --------------------------------------------------------

    for phrase in CUSTOMER_SUPPORT_PHRASES:

        phrase_clean = normalize_text(
            phrase
        )

        if phrase_clean in text:

            score += 2

            matched_keywords.append(
                phrase
            )

    # --------------------------------------------------------
    # Internet/service patterns
    # --------------------------------------------------------

    internet_patterns = [

        "internet not working",
        "internet is not working",
        "internet isnt working",

        "internet does not work",
        "internet doesnt work",

        "internet stopped working",

        "wifi not working",
        "wifi is not working",

        "network not working",
        "network is not working",

        "connection not working",
        "connection is not working",
    ]

    for pattern in internet_patterns:

        if pattern in text:

            score += 4

            matched_keywords.append(
                pattern
            )

            break

    return (
        score,
        matched_keywords,
        nlp
    )


# ============================================================
# NORMAL EMAIL SCORE
# ============================================================

def calculate_normal_score(
    subject,
    body
):

    text = normalize_text(
        subject
        + " "
        + body
    )

    score = 0

    signals = []

    for keyword in NORMAL_EMAIL_KEYWORDS:

        if keyword in text:

            score += 1

            signals.append(
                keyword
            )

    return score, signals


# ============================================================
# MAIN FILTER
# ============================================================

def should_send_to_ai(
    sender,
    subject,
    body
):

    # --------------------------------------------------------
    # RULE 1
    # Automated sender
    # --------------------------------------------------------

    if is_ignored_sender(
        sender
    ):

        return {

            "send_to_ai": False,

            "reason":
                "Automated or ignored sender",

            "matched_keywords": [],

            "corrections": []

        }

    # --------------------------------------------------------
    # Promotion
    # --------------------------------------------------------

    promotion_score, promotion_signals = (
        calculate_promotion_score(
            subject,
            body
        )
    )

    # --------------------------------------------------------
    # Complaint
    # --------------------------------------------------------

    (
        complaint_score,
        complaint_keywords,
        nlp_result
    ) = calculate_complaint_score(
        subject,
        body
    )

    # --------------------------------------------------------
    # Normal
    # --------------------------------------------------------

    normal_score, normal_signals = (
        calculate_normal_score(
            subject,
            body
        )
    )

    # ========================================================
    # COMPLAINT HAS HIGHEST PRIORITY
    # ========================================================

    if complaint_score >= 3:

        return {

            "send_to_ai": True,

            "reason":
                "Potential complaint",

            "matched_keywords":
                complaint_keywords,

            "corrections":
                nlp_result[
                    "corrections"
                ]

        }

    # ========================================================
    # PROMOTION
    # ========================================================

    if promotion_score >= 3:

        return {

            "send_to_ai": False,

            "reason":
                "Promotional/marketing email",

            "matched_keywords":
                promotion_signals,

            "corrections":
                nlp_result[
                    "corrections"
                ]

        }

    # ========================================================
    # NORMAL EMAIL
    # ========================================================

    if normal_score >= 1:

        return {

            "send_to_ai": False,

            "reason":
                "Normal/non-complaint email",

            "matched_keywords":
                normal_signals,

            "corrections":
                nlp_result[
                    "corrections"
                ]

        }

    # ========================================================
    # UNKNOWN
    # ========================================================

    return {

        "send_to_ai": False,

        "reason":
            "No strong complaint signal",

        "matched_keywords": [],

        "corrections":
            nlp_result[
                "corrections"
            ]

    }