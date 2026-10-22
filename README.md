# Email Sentinel AI — Architecture, Security & Operations Guide

An adaptive NLP-based Email Spam Detection and Security Analysis System with real-time Gmail OAuth integration, atomic database persistence, account-isolated predictions, Promotions classification, and controlled model governance.

---

## 1. Project Architecture

The repository consists of four cohesive subsystems:

```text
Email-Sentinel-AI/
├── backend/                  # FastAPI Application & ML Pipelines
│   ├── app/main.py           # REST API endpoints, auth, and CORS
│   ├── config.py             # Environment configuration & security constants
│   ├── content/              # Bad words and content filtering
│   ├── database/             # SQLAlchemy engine, models, and repository
│   ├── email/                # Gmail IMAP sync provider and normalizers
│   ├── ml/                   # LinearSVC classifier, governance, and feedback validator
│   ├── nlp/                  # Word and Character TF-IDF feature extractors
│   └── security/auth.py      # OAuth token verification & HMAC session signing
├── frontend/                 # React + TypeScript + Vite Dashboard
│   ├── src/pages/            # Dashboard, Inbox, Analyze, Analytics, Adaptive, Models
│   ├── src/services/api.ts   # Authenticated API client (credentials: include)
│   └── src/context/          # Theme and application context
├── extension/                # Chrome Extension (Manifest V3)
│   ├── src/auth/             # Google OAuth & launchWebAuthFlow account selection
│   ├── src/background/       # Service worker with Gmail API analysis pipeline
│   ├── src/popup/            # Extension popup UI
│   └── src/services/         # Gmail API message fetcher and label extractor
├── models/                   # Preserved production model artifacts (v1)
├── training/                 # Leakproof dataset construction and candidate training
└── tests/                    # Comprehensive regression and security test suites
```

---

## 2. Environment & Version Requirements

- **Python**: 3.10 to 3.13 (Verified on Python 3.13.5)
- **Node.js**: 18.x or 20.x (LTS)
- **OCR Engine (Optional for Image Analysis)**: Tesseract-OCR v5.x

---

## 3. Installation Instructions

### Backend Setup
```bash
# Create and activate a virtual environment
python -m venv .venv
# Windows PowerShell
.venv\Scripts\Activate.ps1
# Linux/macOS
source .venv/bin/activate

# Install reconciled backend dependencies
pip install -r requirements.txt
```

### Frontend Setup
```bash
cd frontend
npm install
cd ..
```

### Chrome Extension Setup
```bash
cd extension
npm install
npm run build
cd ..
```

---

## 4. Environment Variables Setup

Create a `.env` file in the root directory (never commit `.env` to Git):

```ini
# Application Secrets
SESSION_SECRET_KEY=change-this-to-a-secure-random-32-byte-hex-key
ADMIN_API_KEY=change-this-to-a-secure-admin-api-key
ADMIN_EMAILS=admin@email-sentinel.local

# Google OAuth Configuration
GOOGLE_CLIENT_ID=1044023892905-910jptpfgub2ag6am67ocpgukhcnrgd1.apps.googleusercontent.com

# CORS Configuration (Comma-separated)
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173

# Database URL
DATABASE_URL=sqlite:///./spam_detection.db

# Optional: Tesseract executable path if not in system PATH
# TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe

# Optional: Server-side IMAP credentials (single-account fallback)
# GMAIL_EMAIL=your-service-account@gmail.com
# GMAIL_APP_PASSWORD=your-app-password
```

---

## 5. Running the Application

### 1. Start the FastAPI Backend
```bash
uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```
Backend health check is available at `http://localhost:8000/health`.

### 2. Start the Frontend Dashboard
```bash
cd frontend
npm run dev
```
Dashboard opens at `http://localhost:5173`.

### 3. Load the Chrome Extension
1. Open Google Chrome and navigate to `chrome://extensions/`.
2. Toggle **Developer mode** (top right).
3. Click **Load unpacked** and select the `extension/dist` directory.

---

## 6. Security & Account Isolation Architecture

1. **Server-Side Token Verification**: The backend validates Google access tokens against `https://oauth2.googleapis.com/tokeninfo`, verifying token expiration, audience, and extracting the verified email.
2. **Account Scoping**: Client-provided `account_email` parameters are never blindly trusted. Every email insert, prediction, and statistics lookup is strictly bound to the server-verified account identity.
3. **Cross-Account Protection**:
   - User A cannot view User B's emails.
   - User A cannot view User B's email details.
   - Cross-account feedback submissions return `HTTP 403 Forbidden`.
   - Statistics queries are strictly scoped to the requesting user's records.
4. **Administrative Protection**:
   - Retraining (`POST /models/train-candidate`), model promotion (`POST /models/{version}/promote`), rollback (`POST /models/{version}/rollback`), and IMAP sync (`POST /gmail/sync`) require administrative privileges (`require_admin`).
5. **CORS Restrictions**: Wildcard origins combined with credentials have been removed. Only explicit frontend origins (`http://localhost:5173`) and Chrome Extension origins (`chrome-extension://...`) are permitted.

---

## 7. Database Integrity & Atomic Persistence

- **Atomic Writes**: `Repository.record_email_and_prediction` creates both the `Email` and `Prediction` record within a single database transaction using `session.flush()` and a single `session.commit()`. If prediction insertion fails, the entire transaction is rolled back, preventing orphaned records.
- **Deduplication**: Deduplication is scoped to `(provider, provider_message_id, account_email)`. Repeated analysis reuses existing records without duplicate rows.
- **Database Backup**: Always backup `spam_detection.db` before performing schema modifications:
  ```bash
  Copy-Item spam_detection.db spam_detection.db.bak
  ```

---

## 8. Promotions Category Extraction

- The Chrome extension extracts Gmail category labels (`labelIds` from Gmail API message responses).
- Labels are mapped to categories:
  - `CATEGORY_PROMOTIONS` → `PROMOTIONS`
  - `CATEGORY_SOCIAL` → `SOCIAL`
  - `CATEGORY_UPDATES` → `UPDATES`
  - `CATEGORY_FORUMS` → `FORUMS`
  - Default → `PRIMARY`
- **Display Precedence Policy**: In the Inbox UI, an email in `PROMOTIONS` displays the `PROMOTION` badge. The underlying ML prediction (`SPAM` or `HAM`) and decision score remain preserved and visible in the email detail view.

---

## 9. Google OAuth & Account Switching Configuration

### Google Cloud Console Requirements
To use explicit account selection with `chrome.identity.launchWebAuthFlow`:
1. Navigate to [Google Cloud Console](https://console.cloud.google.com/) -> **APIs & Services** -> **Credentials**.
2. Under OAuth 2.0 Client IDs, open your client ID.
3. Under **Authorized redirect URIs**, add your extension redirect URI:
   ```text
   https://<your-extension-id>.chromiumapp.org/
   ```
   *(Find `<your-extension-id>` on `chrome://extensions` after loading the unpacked extension).*

### Limitations of Single-Credential IMAP
The backend `/gmail/sync` endpoint uses a single set of environment credentials (`GMAIL_EMAIL` and `GMAIL_APP_PASSWORD`). Because IMAP cannot isolate multiple user accounts securely, it is restricted to administrative users. End-users must analyze their mail via the Chrome Extension OAuth flow.

---

## 10. Automated Test Suites

Run the complete test suite:
```bash
# Run all Python backend tests
pytest tests/ -v

# Run extension unit and authentication tests
cd extension
npm run build
node test-auth.js
cd ..

# Run frontend build validation
cd frontend
npm run build
cd ..
```
