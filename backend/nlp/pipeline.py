from sklearn.base import BaseEstimator, TransformerMixin
from backend.nlp.preprocessing import clean_text

class TextCleaner(BaseEstimator, TransformerMixin):
    """
    Scikit-learn compatible transformer for text cleaning.
    """
    def fit(self, X, y=None):
        return self

    def transform(self, X, y=None):
        return [clean_text(text) for text in X]
