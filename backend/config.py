import os

# Configurable minimum feedback threshold for adaptive retraining
# Defaults to 50, but can be overridden by environment variable
ADAPTIVE_MIN_FEEDBACK = int(os.getenv("ADAPTIVE_MIN_FEEDBACK", "50"))

# Base directories
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODELS_DIR = os.path.join(BASE_DIR, "models")
DATASETS_DIR = os.path.join(BASE_DIR, "Datasets")
TRAINING_DIR = os.path.join(BASE_DIR, "training")
