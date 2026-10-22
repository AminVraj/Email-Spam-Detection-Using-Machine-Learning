import os

# Configurable minimum feedback threshold for adaptive retraining
# Defaults to 50, but can be overridden by environment variable
ADAPTIVE_MIN_FEEDBACK = int(os.getenv("ADAPTIVE_MIN_FEEDBACK", "50"))

# Base directories
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODELS_DIR = os.path.join(BASE_DIR, "models")
DATASETS_DIR = os.path.join(BASE_DIR, "Datasets")
TRAINING_DIR = os.path.join(BASE_DIR, "training")

# Security, OAuth and Authorization Configuration
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "1044023892905-910jptpfgub2ag6am67ocpgukhcnrgd1.apps.googleusercontent.com")
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "sentinel-admin-secret-key-change-in-prod")
ADMIN_EMAILS = [e.strip().lower() for e in os.getenv("ADMIN_EMAILS", "admin@email-sentinel.local,admin@gmail.com").split(",") if e.strip()]
SESSION_SECRET_KEY = os.getenv("SESSION_SECRET_KEY", "sentinel-session-secret-key-change-in-prod-32bytes")
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000").split(",") if o.strip()]
TESTING = os.getenv("TESTING", "").lower() in ("1", "true")
