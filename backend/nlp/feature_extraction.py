from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.pipeline import FeatureUnion

def build_nlp_features():
    """
    Builds the feature extraction pipeline combining word and character TF-IDF.
    """
    word_tfidf = TfidfVectorizer(
        analyzer='word',
        ngram_range=(1, 3), # Unigrams, bigrams, and trigrams
        min_df=2,           # Ignore terms that appear in less than 2 documents
        max_df=0.95,        # Ignore terms that appear in more than 95% of documents
        max_features=5000
    )
    
    char_tfidf = TfidfVectorizer(
        analyzer='char_wb',
        ngram_range=(2, 5), # Character 2-grams to 5-grams (catches obfuscation)
        min_df=2,
        max_df=0.95,
        max_features=5000
    )
    
    features = FeatureUnion([
        ('word_features', word_tfidf),
        ('char_features', char_tfidf)
    ])
    
    return features
