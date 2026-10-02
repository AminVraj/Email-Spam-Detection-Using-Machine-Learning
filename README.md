# Email Spam Detection System

An adaptive NLP-based Email Spam Detection System built with Python, scikit-learn, and FastAPI, featuring controlled model evolution and governance.

## Current Architecture
The project is structured into modular components:
- **`backend/nlp`**: Core Natural Language Processing logic (text cleaning, feature extraction).
- **`backend/ml`**: Machine learning model inference, feedback quality validation, and model governance.
- **`backend/app`**: FastAPI endpoints serving predictions, feedback, training trigger, model comparison, promotion, and rollback.
- **`training/`**: Adaptive dataset construction, leakproof data splitting, and model training pipelines.
- **`tests/`**: Automated test suite for NLP pipelines, API endpoints, database operations, and Phase 5 adaptive learning features.
- **`frontend/`**: React, TypeScript, and Tailwind CSS based admin dashboard for model monitoring and governance.

## NLP Pipeline
The classifier does not use manually hardcoded spam rules, keyword lists, or sender blacklists/whitelists. Instead, it relies on a statistical/linguistic NLP pipeline:
1. **Preprocessing**: Normalizes Unicode, URLs, emails, numbers, and currency symbols.
2. **Feature Extraction (Word & Char TF-IDF)**: Extracts Word 1–3 n-grams and Character 2–5 n-grams to capture both linguistic semantics and spam obfuscation (e.g., `fr33`).
3. **Classification**: Advanced Linear SVM model trained on labeled data, providing decision function scores.

## Adaptive Learning Architecture (Phase 5)

The system is designed for controlled, auditable, and leakproof model evolution based on validated user feedback.

```text
Initial Base Dataset (spam.csv)
      │
      ▼
Production Model v1 (models/spam_model_v1.joblib)
      │
      ▼
Real Email Predictions -> User Feedback
      │
      ▼
Feedback Quality Validation Layer
      │
      ▼
Minimum Feedback Threshold Check (ADAPTIVE_MIN_FEEDBACK=50)
      │
      ▼
Combined Training Dataset (Base + Validated Feedback)
      │
      ▼
Candidate Model v2 (models/spam_model_v2.joblib) [status = candidate]
      │
      ▼
Holdout Validation / Test Evaluation & v1 vs v2 Comparison
      │
      ▼
Explicit Promotion (POST /models/v2/promote)
      │
      ▼
Production v2 (status = production) ──> v1 Retained for Rollback (status = archived)
```

> **IMPORTANT**: The system does NOT automatically retrain or replace the production model after every email. Model evolution is strictly controlled, versioned, and requires explicit promotion after passing governance checks.

### Key Adaptive Features

1. **Production Model v1 Protection**: `models/spam_model_v1.joblib` remains intact as a permanent rollback model and is never overwritten or directly modified.
2. **Feedback Quality Validation**: Validates user feedback for training eligibility:
   - Email exists and contains usable training text.
   - User label is valid (`SPAM` or `HAM`).
   - Linked to a valid prediction.
   - Prevents duplicate feedback per email/prediction.
   - Detects content label conflicts (marks for review).
   - Prevents re-using feedback already used in previous training cycles.
3. **Minimum Feedback Threshold**: Retraining triggers only after reaching a configurable minimum amount of new validated feedback (`ADAPTIVE_MIN_FEEDBACK`, default 50).
4. **Data Leakage Prevention**: Prevents text overlap across train and test sets using clean text deduplication and stratified splits.
5. **Factual Model Comparison**: Compares candidate model metrics against production on the same evaluation dataset.
6. **Explicit Model Governance & Promotion**: Promotion requires passing checks (Spam Precision drop <= 0.02, Spam Recall drop <= 0.05, FPR <= 0.02, model loadability, and automated regression tests).
7. **Safe Rollback**: Immediate rollback to any previous version (e.g., `v1`) via `POST /models/{version}/rollback` without retraining.
8. **Observed Outcomes vs Holdout Metrics**: Clearly distinguishes offline holdout test metrics from real-world user-feedback-based observed outcomes (observed FPs, FNs, TPs, TNs).

## API Endpoints

### 1. Core Endpoints
- `GET /health`: Health status.
- `GET /model/info`: Active production model details.
- `POST /predict`: Classify email as SPAM or HAM.
- `POST /ocr`: Extracts text from an uploaded screenshot via Tesseract OCR and normalizes it.
- `POST /feedback`: Record user confirmation or correction (SPAM or HAM).
- `GET /statistics`: Operational predictions, corrections, and user-feedback-based observed outcomes.

### 2. Adaptive Evolution Endpoints (Phase 5)
- `GET /feedback/quality-report`: Quality metrics and training readiness (never exposes raw email text).
- `POST /models/train-candidate`: Triggers adaptive candidate model training (status = `candidate`).
- `GET /models`: Lists all registered model versions and statuses.
- `GET /models/compare/{version}`: Side-by-side metric comparison between production and candidate version.
- `POST /models/{version}/promote`: Explicitly promotes candidate model to production after governance checks.
- `POST /models/{version}/rollback`: Rolls back active production model to specified version.

## Testing
Run the complete automated test suite (67 offline tests covering Phase 1–5):
```bash
pytest tests/ -v
```

## Phase 6 Frontend Dashboard

The Phase 6 frontend dashboard is built with **React**, **TypeScript**, **Vite**, **Tailwind CSS**, and **React Query**.

### Running the Application

**1. Start the FastAPI Backend:**
```bash
python -m uvicorn backend.app.main:app --reload
```

**2. Start the Frontend Dashboard:**
```bash
cd frontend
npm run dev
```

### Frontend Architecture & Pages
- **Dashboard**: High-level overview of processed emails, spam/ham detection counts, and Gmail authentication status.
- **Inbox**: Displays processed emails retrieved from the backend, featuring SPAM/HAM badges and model version tags.
- **Analyze Email**: Manual analysis workspace allowing users to paste suspicious text or upload an email screenshot (OCR) for evaluation against the active production model. Extracted text can be reviewed before triggering the classifier.
- **Analytics**: Visualizes spam distribution and user-observed feedback outcomes.
- **Adaptive Learning**: Monitors the feedback pipeline, showing the current count of validated feedback versus the required threshold for training.
- **Model Management (Admin)**: Allows administrators to trigger candidate model training, run governance evaluations against the production model, and explicitly promote or rollback models.

### Known Limitations
- The current evaluation dataset is SMS-style rather than a representative real-world email corpus.
- The LinearSVC decision score is a raw confidence margin, not a calibrated probability.
- User feedback is treated as validated training feedback, not automatically assumed ground truth.
- Candidate models are not automatically promoted; they require explicit admin approval via the governance UI.
- Gmail sync uses the existing authentication architecture; backend authorization should be strengthened before production deployment.

## Dataset
The current evaluation/training dataset is an SMS spam benchmark dataset (`Datasets/spam.csv`). Dataset source and redistribution terms should be verified according to the original dataset provider before redistribution.

## Privacy & Security
- Full email text is never exposed via API responses, statistics, model metadata, or promotion reports.
- Generated training datasets containing email content remain local and ignored by Git (`.gitignore`).
- The frontend `.env` file does not contain application secrets.
