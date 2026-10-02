# Audit Report and Refactoring Plan

## 1. Current State of the Project
- **Dataset**: `Datasets/spam.csv` containing SMS-style messages with `Category` (ham/spam) and `Message`. Contains 5572 records.
- **Preprocessing & Vectorizer**: Uses `sklearn.feature_extraction.text.CountVectorizer` without any custom preprocessing or normalization (e.g., URLs, emails, or number normalization are missing).
- **Classifier**: `MultinomialNB` from `sklearn.naive_bayes`.
- **Model Storage**: Saved as a Pipeline (vectorizer + classifier) in `Model/EmailSpamTrainedModel.joblib` using `joblib`.
- **Evaluation**: The notebook only evaluates raw accuracy (`clf.score`) using a 75/25 train-test split. It lacks critical metrics like Precision, Recall, F1-score, and confusion matrix.
- **API**: A basic Flask API (`app.py`) with a single endpoint `POST /check_email_spam` that expects `{"email": ["..."]}` and returns `{"spam": true/false}`.
- **Dependencies**: Listed in `requirements.txt` (Flask, joblib, numpy, pandas, scikit-learn).
- **Notebook**: `Code/EmailSpamModel.ipynb` which contains the entire pipeline in a single file.

## 2. Issues & Limitations Identified
- **No proper NLP preprocessing**: Special characters, URLs, and numbers are not handled, meaning obfuscated spam (e.g. `fr33`) might be missed or legitimate emails might be misclassified.
- **No character-level features**: Missing ability to detect obfuscated spam patterns using character n-grams.
- **Weak evaluation**: Relying purely on accuracy for an imbalanced dataset is a poor practice. We need F1, Precision, and Recall.
- **No model comparison**: Only Naive Bayes is evaluated.
- **Coupled architecture**: No clear separation of concerns (NLP pipeline, model registry, training, and inference).

## 3. Migration & Refactoring Plan (Phase 1)
To avoid destructive changes, I will build the new architecture alongside the existing one, moving over to it gradually.

1. **Architecture Creation**: Scaffold `backend/nlp/`, `backend/ml/`, and `training/` directories.
2. **Advanced NLP Pipeline**: Implement `preprocessing.py` and `feature_extraction.py` with custom text normalization and `FeatureUnion` for word/character TF-IDF.
3. **Model Training & Comparison**: Create `training/train.py` to compare Naive Bayes, Logistic Regression, and Linear SVM, evaluating them on Precision, Recall, and F1.
4. **Model Serialization**: Save the best-performing model with metadata.

Once Phase 1 is verified, we will move to Phase 2 (Classification API).
