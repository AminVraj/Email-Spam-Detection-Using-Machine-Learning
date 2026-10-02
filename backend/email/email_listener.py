import time
from imapclient import IMAPClient
import pyzmail

from filter import should_send_to_ai


# ============================================================
# COMPLAINTIQ AI
# REAL-TIME EMAIL LISTENER
# ============================================================
#
# Flow:
#
# Gmail
#   ↓
# is:unread category:primary
#   ↓
# Extract email
#   ↓
# Local NLP + Rule Filter
#   ↓
# Potential Complaint / Ignore
#   ↓
# Mark email as READ
#   ↓
# Next iteration
#
# Gemini is currently DISABLED.
#
# ============================================================


# ============================================================
# GMAIL CONFIGURATION
# ============================================================

import os

EMAIL = os.environ.get("GMAIL_EMAIL", "")

# Put your CURRENT Gmail App Password here.
# Do NOT use your old/revoked App Password.

APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")


# How frequently Gmail should be checked

CHECK_INTERVAL = 10


# ============================================================
# DISPLAY STARTUP INFORMATION
# ============================================================

print("=" * 70)
print("COMPLAINTIQ AI - REAL-TIME EMAIL LISTENER")
print("=" * 70)

print("Gmail Filter : PRIMARY ONLY")
print("Email State  : UNREAD ONLY")
print("NLP Filter   : ENABLED")
print("Spell Check  : ENABLED")
print("Lemmatizer   : ENABLED")
print("Gemini       : DISABLED")
print("After Scan   : MARK AS READ")
print("Status       : LISTENING")
print("=" * 70)


# ============================================================
# EXTRACT EMAIL INFORMATION
# ============================================================

def extract_email_data(server, uid):

    """
    Fetch and extract:

    - Sender
    - Subject
    - Body
    """

    raw = server.fetch(
        [uid],
        ["BODY[]"]
    )

    message = pyzmail.PyzMessage.factory(
        raw[uid][b"BODY[]"]
    )


    # ========================================================
    # SENDER
    # ========================================================

    addresses = message.get_addresses("from")

    if addresses:

        sender = addresses[0][1]

    else:

        sender = "Unknown"


    # ========================================================
    # SUBJECT
    # ========================================================

    subject = message.get_subject()

    if not subject:

        subject = "(No Subject)"


    # ========================================================
    # BODY
    # ========================================================

    body = ""


    # --------------------------------------------------------
    # Prefer plain-text body
    # --------------------------------------------------------

    if message.text_part:

        try:

            body = message.text_part.get_payload(
                decode=True
            )

            if isinstance(body, bytes):

                charset = message.text_part.charset

                if charset:

                    body = body.decode(
                        charset,
                        errors="replace"
                    )

                else:

                    body = body.decode(
                        "utf-8",
                        errors="replace"
                    )


        except Exception as e:

            print(
                "⚠ Could not decode text body:",
                e
            )

            body = "Could not read email body."


    # --------------------------------------------------------
    # If no plain text, use HTML
    # --------------------------------------------------------

    elif message.html_part:

        try:

            body = message.html_part.get_payload(
                decode=True
            )

            if isinstance(body, bytes):

                charset = message.html_part.charset

                if charset:

                    body = body.decode(
                        charset,
                        errors="replace"
                    )

                else:

                    body = body.decode(
                        "utf-8",
                        errors="replace"
                    )


        except Exception as e:

            print(
                "⚠ Could not decode HTML body:",
                e
            )

            body = "Could not read HTML email body."


    # --------------------------------------------------------
    # No body
    # --------------------------------------------------------

    else:

        body = "No readable email body."


    return sender, subject, body


# ============================================================
# DISPLAY FILTER RESULT
# ============================================================

def display_filter_result(result):

    """
    Display the result returned by filters.py.
    """

    print("\n")
    print("=" * 70)
    print("LOCAL NLP FILTER RESULT")
    print("=" * 70)


    # ========================================================
    # SEND TO AI
    # ========================================================

    if result["send_to_ai"]:

        print(
            "🟢 SEND TO AI"
        )

        print(
            "Reason:",
            result["reason"]
        )


        # ----------------------------------------------------
        # Complaint keywords
        # ----------------------------------------------------

        if result.get("matched_keywords"):

            print(
                "Complaint Keywords:",
                ", ".join(
                    result["matched_keywords"]
                )
            )


        # ----------------------------------------------------
        # Spell corrections
        # ----------------------------------------------------

        if result.get("corrections"):

            print(
                "Spell Corrections:"
            )

            for correction in result["corrections"]:

                print(
                    "  •",
                    correction
                )


        print()
        print(
            "Gemini is currently DISABLED."
        )

        print(
            "This email would be sent to Gemini."
        )


    # ========================================================
    # IGNORE
    # ========================================================

    else:

        print(
            "🔴 IGNORE"
        )

        print(
            "Reason:",
            result["reason"]
        )


        # ----------------------------------------------------
        # Show detected signals
        # ----------------------------------------------------

        if result.get("matched_keywords"):

            print(
                "Detected Signals:",
                ", ".join(
                    result["matched_keywords"]
                )
            )


        # ----------------------------------------------------
        # Show spell corrections
        # ----------------------------------------------------

        if result.get("corrections"):

            print(
                "Spell Corrections:"
            )

            for correction in result["corrections"]:

                print(
                    "  •",
                    correction
                )


# ============================================================
# MAIN EMAIL LISTENER
# ============================================================

while True:

    try:

        print("\n")
        print("=" * 70)
        print("Checking Gmail...")
        print("=" * 70)


        # ====================================================
        # CONNECT TO GMAIL
        # ====================================================

        with IMAPClient(
            "imap.gmail.com"
        ) as server:


            # =================================================
            # LOGIN
            # =================================================

            server.login(
                EMAIL,
                APP_PASSWORD
            )


            print(
                "✓ Gmail connected."
            )


            # =================================================
            # OPEN INBOX
            # =================================================

            server.select_folder(
                "INBOX"
            )


            # =================================================
            # SEARCH GMAIL
            # =================================================
            #
            # This is the most important line.
            #
            # Gmail itself performs:
            #
            # is:unread
            #
            # AND
            #
            # category:primary
            #
            # Therefore:
            #
            # READ email      → NOT returned
            # UNREAD email    → returned
            #
            # PRIMARY         → returned
            # PROMOTIONS      → NOT returned
            # SOCIAL          → NOT returned
            # UPDATES         → NOT returned
            # FORUMS          → NOT returned
            #
            # =================================================

            messages = server.gmail_search(
                "is:unread category:primary"
            )


            # =================================================
            # NO NEW EMAIL
            # =================================================

            if not messages:

                print(
                    "No new Primary emails."
                )


            # =================================================
            # NEW EMAILS FOUND
            # =================================================

            else:

                print(
                    f"Found {len(messages)} "
                    f"new Primary email(s)."
                )


                # =================================================
                # PROCESS EMAILS ONE BY ONE
                # =================================================

                for index, uid in enumerate(
                    messages,
                    start=1
                ):

                    try:

                        # ========================================
                        # EXTRACT EMAIL
                        # ========================================

                        (
                            sender,
                            subject,
                            body
                        ) = extract_email_data(
                            server,
                            uid
                        )


                        # ========================================
                        # DISPLAY EMAIL
                        # ========================================

                        print("\n")
                        print("=" * 70)

                        print(
                            f"EMAIL {index}/{len(messages)}"
                        )

                        print("=" * 70)

                        print(
                            "From    :",
                            sender
                        )

                        print(
                            "Subject :",
                            subject
                        )


                        # ========================================
                        # RUN LOCAL NLP + RULE FILTER
                        # ========================================

                        result = should_send_to_ai(
                            sender,
                            subject,
                            body
                        )


                        # ========================================
                        # DISPLAY RESULT
                        # ========================================

                        display_filter_result(
                            result
                        )


                        # ========================================
                        # MARK EMAIL AS READ
                        # ========================================
                        #
                        # Once this is done:
                        #
                        # is:unread
                        #
                        # will no longer return this email.
                        #
                        # Therefore the same email will NOT
                        # appear during the next iteration.
                        #
                        # ========================================

                        server.add_flags(
                            uid,
                            ["\\Seen"]
                        )


                        print()
                        print(
                            "✓ Email marked as READ."
                        )

                        print("=" * 70)


                    except Exception as email_error:

                        print("\n")
                        print(
                            "⚠ Error processing email:"
                        )

                        print(
                            email_error
                        )

                        print("=" * 70)


            # =================================================
            # WAIT
            # =================================================

            print()
            print(
                f"Next Gmail check in "
                f"{CHECK_INTERVAL} seconds..."
            )

            time.sleep(
                CHECK_INTERVAL
            )


    # ========================================================
    # GMAIL CONNECTION ERROR
    # ========================================================

    except Exception as e:

        print("\n")
        print("=" * 70)
        print("⚠ GMAIL CONNECTION ERROR")
        print("=" * 70)

        print(
            e
        )

        print()
        print(
            "Retrying in 10 seconds..."
        )

        time.sleep(
            10
        )