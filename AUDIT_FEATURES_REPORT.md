# Email Sentinel AI — Comprehensive Feature-by-Feature Audit Report

**Date of Audit**: October 2026
**Auditor**: Senior Software Architect, ML Engineer, QA Engineer, Security Reviewer, and Chrome Extension Developer
**Audit Mode**: Audit-First (Evidence-Based Verification, Zero Modification to Model/DB/Credentials)

---

## 1. Executive Summary

This report presents an independent, evidence-based audit of the **Email Sentinel AI** codebase. Previous historical sessions reported passing 82/82 tests, complete Promotions classification, Bad Words Protection, Light/Dark theme, and Chrome Extension Gmail OAuth integration with account switching and dashboard redirection.

### Key Verified Facts
1. **Automated Test Suite**: 85 passing backend unit/integration tests (`python -m pytest tests -v` took 48.89s, 85 passed, 0 failures, 152 deprecation warnings). This is higher than the historical claim of 82/82 due to added tests for account switching and OCR/bad words.
2. **Frontend Quality & Build**: `frontend/` builds cleanly with 0 TypeScript errors (`tsc -b && vite build` succeeded in 2.88s). Linter (`oxlint`) passed with 0 errors and 1 fast-refresh warning in `ThemeContext.tsx`.
3. **Extension Quality & Build**: `extension/` compiles cleanly (`tsc && node build.js`). Extension authentication unit test suite (`test-auth.js`) passed 8/8 tests with simulated Chrome Identity and fetch mocking.
4. **Machine Learning Pipeline**: Advanced Linear Support Vector Machine (`LinearSVC`) with dual Word (1–3 n-grams) and Character (2–5 n-grams) TF-IDF feature union is active in `models/spam_model_v1.joblib` and metadata in `models/metadata_v1.json`. Decision scores are strictly preserved as continuous margins from `decision_function`, never fabricated as calibrated probabilities.
5. **Adaptive Learning & Governance**: Complete implementation of feedback validation (contradiction detection, deduplication, non-reuse), leakproof dataset construction, candidate training, promotion evaluation against strict degradation thresholds, and non-destructive rollback.
6. **Bad Words Protection & OCR**: Word-boundary prohibited word filtering (`BadWordDetector`) properly aborts execution with HTTP 400 before classifier invocation or DB insertion. Tesseract OCR v5.4.0 is installed locally and functional.

### Critical Discrepancies & Architectural Gaps
1. **Chrome Extension Category Gap**: The Chrome Extension (`extension/src/services/gmail-api.ts`) does **not** extract `labelIds` from the Gmail API response and does not supply `provider_category` to `/predict`. Consequently, all emails synced via the Chrome extension default to `provider_category="PRIMARY"`, bypassing the backend's promotions separation logic.
2. **Two Competing Gmail Sync Architectures**:
   - *Extension flow*: Uses Google OAuth2 (`chrome.identity.getAuthToken`), fetches messages in browser, and POSTs each to `/predict`.
   - *Web Dashboard "Sync Gmail" flow*: Uses backend IMAP credentials (`GMAIL_EMAIL` and `GMAIL_APP_PASSWORD` via `IMAPClient`) calling `/gmail/sync`. If `.env` credentials are absent, the dashboard reports "Gmail Disconnected" and disables the sync button, regardless of Chrome extension status.
3. **Chrome Identity API Real-Account Limitation**: `chrome.identity.clearAllCachedAuthTokens()` and server-side revocation clear cached tokens but do **not** sign the user out of their Chrome browser profile. In Google Chrome, `getAuthToken({ interactive: true })` does not support `prompt=select_account` and will automatically re-authenticate the primary Chrome profile account. True multi-account switching requires `chrome.identity.launchWebAuthFlow`.
4. **Backend Authorization & Cross-Account Isolation**: `GET /emails` and `GET /statistics` take no authentication tokens or user filtering. Any client on the network can view all stored emails and predictions across all accounts.
5. **Non-Atomic Database Writes**: In `Repository.record_email_and_prediction`, `email` is committed before `prediction` is created. If prediction persistence fails, an orphan email record is permanently stored.
6. **Obsolete Root Configuration Files**:
   - `requirements.txt` is the legacy file from the original project listing `Flask==2.2.2` (missing FastAPI, Uvicorn, SQLAlchemy, Pillow, etc.).
   - `Dockerfile` attempts to copy non-existent `app.py` and run Flask on port 5000.
   - `.gitignore` lines 32–34 contain spaced characters (` e x t e n s i o n / d i s t / `).
   - `backend/email/` contains 1,692 lines of dead code (`email_listener.py` and `filter.py`) belonging to an unrelated project ("ComplaintIQ AI").

---

## 2. Complete Project Architecture & Data Flow

```
┌────────────────────────────────────────────────────────────────────────┐
│                          CHROME EXTENSION                              │
│                                                                        │
│   Popup UI ──> google-auth.ts ──> chrome.identity.getAuthToken         │
│         │               │                                              │
│         │               ▼                                              │
│         └──> service-worker.ts                                         │
│                     │                                                  │
│                     ├──> gmail-api.ts ──> https://gmail.googleapis.com │
│                     │                        (OAuth2 ReadOnly)         │
│                     │                                                  │
│                     └──> POST http://127.0.0.1:8000/predict            │
│                             │                                          │
│                             ▼                                          │
│                     chrome.tabs.create(http://localhost:5173/inbox)    │
└─────────────────────────────┼──────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        FASTAPI BACKEND (:8000)                         │
│                                                                        │
│   Endpoints:                                                           │
│   • POST /predict           • GET /emails & GET /emails/{id}           │
│   • POST /analyze-manual    • POST /feedback                           │
│   • POST /ocr               • GET /statistics                          │
│   • GET /model/info         • GET /feedback/quality-report             │
│   • POST /gmail/sync (IMAP) • POST /models/train-candidate             │
│   • GET /gmail/auth/status  • POST /models/{version}/promote           │
│                             • POST /models/{version}/rollback          │
│                                                                        │
│   NLP Pipeline (Inference):                                            │
│     normalize_email_body() -> TextCleaner() -> FeatureUnion            │
│       ├─ Word TF-IDF (1-3 ngrams)                                      │
│       └─ Char TF-IDF (2-5 ngrams)                                      │
│     -> LinearSVC.decision_function()                                   │
│                                                                        │
│   Database: SQLite (spam_detection.db)                                 │
│     Tables: emails, predictions, feedback, model_versions              │
└─────────────────────────────▲──────────────────────────────────────────┘
                              │
                              ▼
┌────────────────────────────────────────────────────────────────────────┐
│                     REACT / VITE DASHBOARD (:5173)                     │
│                                                                        │
│   Pages:                                                               │
│   • / (Dashboard Overview: Stats, Auth status, IMAP Sync trigger)      │
│   • /inbox (Split-view list & detail, SPAM/HAM/PROMO filters, search)  │
│   • /analyze (Manual text paste & screenshot OCR with Bad Words guard) │
│   • /analytics (Distributions, Observed user feedback outcomes)        │
│   • /adaptive (Validation pipeline, threshold progress bar)            │
│   • /models (Candidate training, metrics comparison, promotion/roll)   │
│                                                                        │
│   State & Theming: TanStack Query, ThemeContext (light/dark switch)    │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Scorecard & Weighted Completion

| Area | Weight | Status | % Done | Weighted % | Basis of Assessment |
|---|---:|:---:|---:|---:|---|
| **ML model and NLP pipeline** | 15% | VERIFIED (Benchmark) | 85% | 12.75% | LinearSVC artifact exists, FeatureUnion (Word+Char TF-IDF) loaded, decision scores preserved, label mapping clean. Model evaluated only on SMS dataset (`spam.csv`); unverified on diverse RFC-5322 email corpora. |
| **Backend and database** | 15% | PARTIAL | 80% | 12.00% | FastAPI initializes with 21 routes. Deduplication works by `provider_message_id`. Non-atomic multi-commit in `record_email_and_prediction`. Lack of account-based scoping on `GET /emails` and `GET /statistics`. |
| **Gmail integration and OAuth** | 15% | IMPLEMENTED, NOT FULLY VERIFIED | 60% | 9.00% | Unit tests pass with mocks (8/8). Real OAuth execution cannot be completed in headless/non-interactive CLI. Dual competing Gmail sync paths (OAuth in extension vs IMAP in backend). |
| **Chrome extension and account switching** | 15% | IMPLEMENTED, NOT FULLY VERIFIED | 65% | 9.75% | Builds cleanly with TypeScript. Disconnect & token revocation implemented. Redirection to `/inbox` on success. Chrome Identity API limitation prevents forced account selection without `launchWebAuthFlow`. Missing `labelIds` extraction. |
| **Dashboard and persistent results** | 15% | VERIFIED | 90% | 13.50% | Builds with 0 TS errors. Inbox split view displays messages from DB. Filtering by ALL/SPAM/HAM/PROMOTION, text search, feedback confirmation, model management, and analytics fully functional. |
| **Promotions separation** | 5% | PARTIAL | 60% | 3.00% | Backend repository and frontend inbox separate promotions from spam/ham without double-counting. But Chrome extension fails to capture Gmail category label, defaulting all extension emails to PRIMARY. |
| **Bad Words Protection and OCR** | 8% | VERIFIED | 95% | 7.60% | Word-boundary checking blocks inappropriate language with HTTP 400. Frontend warning banner renders. Classifier and DB are bypassed. Tesseract v5.4.0 verified locally. |
| **Adaptive learning and governance** | 7% | VERIFIED | 95% | 6.65% | 19/19 tests pass. Feedback validator detects duplicates and conflicts. Leakproof train/test split. Candidate isolation, governance thresholds, explicit promotion, and non-destructive rollback verified. |
| **Testing, security, and deployment readiness** | 5% | PARTIAL | 50% | 2.50% | 85 tests pass, but `requirements.txt` lists Flask, `Dockerfile` is broken, dead code exists, CORS is open, and API endpoints lack authentication. |
| **TOTAL** | **100%** | **FUNCTIONAL MVP** | — | **76.75%** | **Overall project is ~77% complete and operational as a prototype, with key integration and deployment gaps.** |

---

## 4. Feature-by-Feature Detailed Audit

### A. Machine Learning Spam Detection
- **Model Artifact**: `models/spam_model_v1.joblib` (445,024 bytes) and `models/metadata_v1.json` (1,398 bytes) exist and load successfully via `joblib.load`.
- **Pipeline Architecture**:
  - `backend/nlp/preprocessing.py`: `clean_text` applies NFKD normalization, lowercasing, regex replacement of URLs (`__url__`), emails (`__email__`), numbers (`__number__`), and currency (`__currency__`).
  - `backend/nlp/feature_extraction.py`: `FeatureUnion` combining:
    - Word TF-IDF: (1, 3) n-grams, `min_df=2`, `max_df=0.95`, `max_features=5000`.
    - Character TF-IDF: (2, 5) n-grams with `analyzer='char_wb'`, `min_df=2`, `max_df=0.95`, `max_features=5000`.
  - Classifier: `LinearSVC(random_state=42, dual=False)`.
- **Inference (`backend/ml/predict.py`)**:
  - `predict_email` maps prediction `1` or `"SPAM"` to `"SPAM"`, else `"HAM"`.
  - `decision_score` is retrieved via `self.model.decision_function([combined_text])[0]`. It is explicitly exposed as a floating-point score and **not** converted into a misleading pseudo-probability.
- **Edge Cases Tested**:
  - Empty subject & body -> HTTP 400 (`"Email subject and body cannot both be empty"`).
  - Subject only -> 200 OK.
  - Body only -> 200 OK.
  - Body > 100,000 characters -> HTTP 400 (`"Email body exceeds maximum allowed length"`).
  - Unicode text (e.g. `Hello 🌍! 漢字`) -> 200 OK.
  - HTML tags -> cleaned with `normalize_email_body`, 200 OK.
- **Dataset Reality**: Training and validation were conducted on `Datasets/spam.csv` (5,572 SMS messages: 4,825 ham, 747 spam). Accuracy on SMS data (99.19%) does **not** guarantee equivalent performance on real email formats (HTML headers, disclaimers, forward chains).
- **Status**: **VERIFIED** (on benchmark corpus) / **IMPLEMENTED, NOT FULLY VERIFIED** (on real email corpora).

---

### B. Backend and Database
- **Framework**: FastAPI 0.141.1 running on Python 3.13.5.
- **Initialization**: `init_db()` in `backend/database/database.py` generates SQLite tables (`emails`, `predictions`, `feedback`, `model_versions`) and executes non-destructive column migrations (`account_email`, `training_data_summary`, `feedback_count_used`, `parent_model_version`).
- **Persistence & Deduplication (`backend/database/repository.py`)**:
  - When `provider_message_id` is supplied (e.g., from Gmail), `get_email_by_provider_message_id` checks for existing records scoped by `account_email`. If found, existing `(email.id, prediction.id)` is returned without duplicating database entries.
  - If `provider_message_id` is omitted, deduplication is bypassed even though `body_hash` is computed.
- **Transaction Safety Concern**:
  - In `Repository.record_email_and_prediction` (lines 62–74), `self.db.add(email)` and `self.db.commit()` occur *before* `self.db.add(prediction)` and `self.db.commit()`. If an exception occurs during prediction creation, an orphaned email with no prediction remains in the database.
- **Feedback Linkage**:
  - `Feedback` records link to `email_id` and `prediction_id`.
  - Duplicate feedback for the same `email_id` raises `ValueError("Feedback already recorded for email_id ...")` and returns HTTP 400.
  - Invalid label (not `SPAM` or `HAM`) returns HTTP 400.
- **Multi-Account Scoping**:
  - `account_email` is properly recorded in `emails` table.
  - However, `GET /emails` and `GET /statistics` do not filter by account email; all accounts' emails are returned globally.
- **Status**: **PARTIAL** (Functional, but non-atomic commit and missing tenant query isolation).

---

### C. Gmail Integration and Chrome Extension
- **Extension Architecture**:
  - Built with Manifest V3 (`extension/manifest.json`).
  - Permissions: `"identity"`, `"tabs"`. Host permissions: `https://gmail.googleapis.com/*`, `http://127.0.0.1:8000/*`, `http://localhost:8000/*`, `http://localhost:5173/*`.
  - Scopes: `"https://www.googleapis.com/auth/gmail.readonly"`.
- **Authentication Flow (`extension/src/auth/google-auth.ts`)**:
  - `signIn()` invokes `chrome.identity.getAuthToken({ interactive: true })`.
  - `signOut()`:
    1. Revokes token via `POST https://oauth2.googleapis.com/revoke?token=...`.
    2. Removes cached token via `chrome.identity.removeCachedAuthToken`.
    3. Calls `chrome.identity.clearAllCachedAuthTokens()`.
  - Verification: 8/8 tests passed in `test-auth.js`.
- **Chrome Identity API Real-Account Limitation**:
  - `chrome.identity.clearAllCachedAuthTokens()` clears Chrome's OAuth token cache, but **does not sign the user out of their Google Account or Chrome Profile**.
  - When `getAuthToken({ interactive: true })` is subsequently called, Chrome automatically selects the primary Google profile account without presenting an account chooser modal. To force account selection, `chrome.identity.launchWebAuthFlow` with `prompt=select_account` is required.
- **Message Fetching & Parsing (`extension/src/services/gmail-api.ts`)**:
  - Queries `https://gmail.googleapis.com/gmail/v1/users/me/messages?maxResults=20&q=in:anywhere`.
  - Retrieves full message payload (`format=full`), decodes Base64Url headers, and extracts plain text or HTML bodies.
  - **Identified Gap**: `GmailMessageResponse` does not include `labelIds`. Gmail category labels (such as `CATEGORY_PROMOTIONS`) are discarded, and `predictEmail` sends no `provider_category`.
- **Redirection Logic (`extension/src/background/service-worker.ts`)**:
  - `analyzeGmail()` runs prediction for each message against `http://127.0.0.1:8000/predict`.
  - If backend is down or all predictions fail, the process aborts with an error and **does not** open the dashboard.
  - If analysis succeeds, `chrome.tabs.create({ url: "http://localhost:5173/inbox", active: true })` opens and focuses the dashboard inbox tab.
- **Status**: **IMPLEMENTED, NOT FULLY VERIFIED** (Mock tests pass; real Google OAuth interactive execution cannot be executed in headless environments; `labelIds` category extraction is missing).

---

### D. Dashboard Integration
- **Framework**: React 19, TypeScript 6, Vite 8, Tailwind CSS 4, TanStack Query 5.
- **Persistence Verification**:
  - Analysis results from the Chrome extension or backend sync are stored in SQLite and loaded via `api.getEmails()` (`GET /emails?limit=100`).
  - Refreshing the web page retains all previous predictions, scores, and feedback.
- **Inbox Page (`frontend/src/pages/Inbox.tsx`)**:
  - Split-view interface: left list, right detail panel.
  - Displays sender, subject, received date, SPAM / HAM / PROMOTION badges, decision score, and model version.
  - Interactive search bar filters sender and subject dynamically.
  - Quick filter buttons: `ALL`, `SPAM`, `HAM`, `PROMOTION`.
  - Detail view provides feedback action buttons ("Confirm SPAM" / "Mark as SPAM", "Confirm HAM" / "Mark as HAM").
  - On feedback submission, TanStack Query invalidates `["email", id]`, `["statistics"]`, and `["feedback-quality"]`, immediately updating metrics.
- **Dashboard Overview (`frontend/src/pages/Dashboard.tsx`)**:
  - Summary cards for Total Emails, Detected Spam, Clean Emails (Ham), Promotions, and User Corrections.
  - Active model version and observed false positive/negative counts.
- **Status**: **VERIFIED**.

---

### E. Promotions Separation
- **Conceptual Separation**:
  - Backend `Email` table stores `provider_category` (`"PRIMARY"`, `"PROMOTIONS"`).
  - Backend `Prediction` table independently stores the ML prediction (`"HAM"`, `"SPAM"`).
- **Display Precedence**:
  - In `backend/app/main.py` (`GET /emails` and `GET /emails/{id}`):
    ```python
    classification = pred.classification if pred else "UNKNOWN"
    if getattr(e, "provider_category", "PRIMARY") == "PROMOTIONS":
        classification = "PROMOTION"
    ```
  - Display `classification` shows `"PROMOTION"` to keep promotional newsletters separate from critical inbox messages, while `ml_prediction` retains `"HAM"` or `"SPAM"`.
- **Statistics Isolation**:
  - In `Repository.get_statistics()`, `spam_predictions` and `ham_predictions` filter for `Email.provider_category != "PROMOTIONS"`.
  - Promotional emails are counted separately in `promotions_count`.
  - Prevents marketing newsletters from polluting the core spam detection statistics.
- **Observed Gap**: The Chrome Extension does not read Gmail's `labelIds`, so extension-synced promotional emails are treated as `"PRIMARY"`.
- **Status**: **PARTIAL** (Backend and UI logic complete; Chrome Extension ingestion pipeline missing category tag extraction).

---

### F. Bad Words Protection
- **Module**: `backend/content/bad_word_detector.py` and `backend/content/bad_words.py`.
- **Implementation**:
  - Uses `re.findall(r'\b\w+\b', text.lower())` to extract discrete words.
  - Compares against prohibited words (`offensiveword`, `badword`, `inappropriate`, `profanity`, `nsfw`).
  - Word boundaries prevent false positives on substrings (e.g. words containing "pass" or "class").
- **Enforcement Endpoints**:
  - `POST /analyze-manual`
  - `POST /ocr`
- **Behavior on Detection**:
  - Returns HTTP 400 with payload:
    ```json
    {
      "blocked": true,
      "reason": "BAD_WORD_DETECTED",
      "detected_count": 1
    }
    ```
  - Early exit occurs before `get_classifier()` is invoked.
  - No records are written to `emails`, `predictions`, or `feedback`.
  - Frontend (`AnalyzeEmail.tsx`) intercepts the `blocked: true` response and renders a warning banner.
- **Status**: **VERIFIED**.

---

### G. OCR and Manual Analysis
- **Engine**: Tesseract OCR v5.4.0 (verified locally at `%LOCALAPPDATA%\Programs\Tesseract-OCR\tesseract.exe`).
- **Processing**:
  - `POST /ocr` accepts multipart file upload, reads image bytes via `PIL.Image.open()`, and executes `pytesseract.image_to_string()`.
  - Output is cleaned using `normalize_email_body()`.
  - Bad words detector checks the extracted text.
  - Frontend allows the user to review and edit extracted text in a textarea before clicking "Analyze Content".
- **Database Safety**:
  - Neither `/analyze-manual` nor `/ocr` creates records in `emails` or `predictions`, ensuring ad-hoc tests do not contaminate inbox metrics or training data.
- **Status**: **VERIFIED**.

---

### H. Adaptive Learning and Model Governance
- **Feedback Quality Validation (`backend/ml/feedback_validator.py`)**:
  - Requires user label to be `SPAM` or `HAM`.
  - Verifies email and prediction exist and email has non-empty text.
  - Detects duplicate feedback on the same email.
  - Detects conflicting labels for identical text strings.
  - Prevents feedback re-use across multiple training iterations.
- **Leakproof Dataset Construction (`training/adaptive_dataset.py`)**:
  - Merges base dataset (`spam.csv`) with validated user feedback.
  - `split_training_data_leakproof` groups by clean text, stratifies unique texts, and verifies zero text overlap between train and test sets.
- **Candidate Training (`training/train_adaptive.py`)**:
  - Trains candidate `LinearSVC` with identical NLP feature extraction.
  - Evaluates train and test accuracy, precision, recall, F1, FPR, and confusion matrix.
  - Saves `spam_model_{version}.joblib` and `metadata_{version}.json`.
  - Registers candidate in database with `status = "candidate"`.
  - Hard safety check prevents overwriting `spam_model_v1.joblib`.
- **Governance & Promotion (`backend/ml/model_governance.py`)**:
  - Candidate model is **never** automatically promoted to production.
  - Promotion requires passing checks:
    - Spam Precision drop <= 0.02 (and >= 0.90)
    - Spam Recall drop <= 0.05 (and >= 0.85)
    - False Positive Rate <= 0.02
    - Automated regression smoke tests pass
- **Safe Rollback**:
  - Immediate rollback to `v1` or any prior model version without retraining via `POST /models/{version}/rollback`.
- **Status**: **VERIFIED** (19/19 tests in `test_phase5_adaptive.py` pass).

---

### I. Theme and Frontend Quality
- **Theme Management**:
  - `ThemeContext.tsx` supports `"light"` and `"dark"` modes.
  - Persists preference in `localStorage.getItem("theme")`.
  - Detects OS preference via `window.matchMedia("(prefers-color-scheme: dark)")`.
  - Applies `light` or `dark` class to `document.documentElement`.
- **Layout & Responsiveness**:
  - Sidebar layout with active route indicator.
  - Dark mode styles implemented across all pages, cards, tables, inputs, and modals.
- **Build & Lint Results**:
  - `npm run build`: 0 TypeScript errors; bundle size 355.08 kB (gzip: 105.34 kB).
  - `npm run lint`: 0 errors; 1 warning regarding React fast-refresh in `ThemeContext.tsx`.
- **Status**: **VERIFIED**.

---

### J. Security and Deployment Readiness
- **Secret Management**:
  - `.env` is excluded from git.
  - No OAuth client secrets or user passwords are hardcoded in git tracking.
- **Permissions Minimization**:
  - Extension requests only `identity`, `tabs`, and read-only Gmail access (`https://www.googleapis.com/auth/gmail.readonly`).
- **Data Protection**:
  - API responses for statistics, quality reports, and models omit full email bodies.
  - HTML content is sanitized with `BeautifulSoup` and entity decoding before inference.
- **Identified Vulnerabilities**:
  - **No API Authentication**: FastAPI has no API keys, JWTs, or session cookies. Any local or network process can query `/emails` or trigger model rollback.
  - **Overly Permissive CORS**: `allow_origins=["*"]` with `allow_credentials=True` in `backend/app/main.py`.
  - **Outdated Dependencies**: `requirements.txt` specifies obsolete Flask dependencies instead of FastAPI stack.
  - **Dead Code**: `backend/email/email_listener.py` and `backend/email/filter.py` (1,692 lines from ComplaintIQ AI) should be purged.
- **Status**: **PARTIAL** (Core security measures in place; authorization and deployment hardening required).

---

## 5. Verification Commands Executed & Observed Results

| # | Command | Working Directory | Observed Result |
|---|---|---|---|
| 1 | `python -m pytest tests -v` | Workspace Root | **85 passed, 152 warnings in 48.89s** |
| 2 | `npm run lint` | `frontend/` | **0 errors, 1 warning** (`ThemeContext.tsx` fast-refresh) |
| 3 | `npm run build` | `frontend/` | **0 errors, built in 2.88s** (Bundle: 355.08 kB) |
| 4 | `npm run build` | `extension/` | **0 errors** (`tsc && node build.js`) |
| 5 | `node test-auth.js` | `extension/` | **8/8 authentication tests passed** |
| 6 | `tesseract --version` | Local AppData | **tesseract v5.4.0.20240606 functional** |
| 7 | `python check_routes.py` | Scratch Dir | **21 FastAPI routes confirmed active** |
| 8 | `python inspect_db.py` | Scratch Dir | **DB verified: 94 emails, 94 predictions, 3 feedback, 1 model (v1)** |
