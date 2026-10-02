import os
import sys
import json
import pandas as pd
import joblib
from datetime import datetime
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.naive_bayes import MultinomialNB
from sklearn.linear_model import LogisticRegression
from sklearn.svm import LinearSVC
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.metrics import classification_report, accuracy_score, precision_score, recall_score, f1_score, confusion_matrix

# Add project root to path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.nlp.pipeline import TextCleaner
from backend.nlp.feature_extraction import build_nlp_features

def main():
    print("Loading dataset...")
    data_path = os.path.join(os.path.dirname(__file__), '..', 'Datasets', 'spam.csv')
    data = pd.read_csv(data_path)
    
    # Preprocessing target
    data['Spam'] = data['Category'].apply(lambda x: 1 if x == 'spam' else 0)
    
    # Train/Validation Split (80/20)
    X = data['Message']
    y = data['Spam']
    X_train, X_val, y_train, y_val = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
    
    # Class distribution info
    class_dist = y.value_counts().to_dict()
    val_class_dist = y_val.value_counts().to_dict()
    
    print(f"Training set: {len(X_train)} samples")
    print(f"Validation set: {len(X_val)} samples")
    
    # Baseline Pipeline (The original project's approach)
    baseline_pipeline = Pipeline([
        ('vectorizer', CountVectorizer()),
        ('classifier', MultinomialNB())
    ])
    
    # Candidate models for the new advanced NLP pipeline
    models_to_evaluate = {
        'Baseline (CountVec+NB)': baseline_pipeline,
        'Advanced Naive Bayes': Pipeline([
            ('cleaner', TextCleaner()),
            ('features', build_nlp_features()),
            ('classifier', MultinomialNB())
        ]),
        'Advanced Logistic Regression': Pipeline([
            ('cleaner', TextCleaner()),
            ('features', build_nlp_features()),
            ('classifier', LogisticRegression(max_iter=1000, random_state=42))
        ]),
        'Advanced Linear SVM': Pipeline([
            ('cleaner', TextCleaner()),
            ('features', build_nlp_features()),
            ('classifier', LinearSVC(random_state=42, dual=False))
        ])
    }
    
    results = []
    
    for name, pipeline in models_to_evaluate.items():
        print(f"\nTraining {name}...")
        
        # Fit on training data ONLY
        pipeline.fit(X_train, y_train)
        
        # Predict on validation
        y_pred = pipeline.predict(X_val)
        
        # Calculate detailed metrics
        acc = accuracy_score(y_val, y_pred)
        
        # 0 = Ham, 1 = Spam
        tn, fp, fn, tp = confusion_matrix(y_val, y_pred).ravel()
        
        spam_precision = precision_score(y_val, y_pred, pos_label=1, zero_division=0)
        spam_recall = recall_score(y_val, y_pred, pos_label=1, zero_division=0)
        spam_f1 = f1_score(y_val, y_pred, pos_label=1, zero_division=0)
        
        ham_precision = precision_score(y_val, y_pred, pos_label=0, zero_division=0)
        ham_recall = recall_score(y_val, y_pred, pos_label=0, zero_division=0)
        ham_f1 = f1_score(y_val, y_pred, pos_label=0, zero_division=0)
        
        macro_f1 = f1_score(y_val, y_pred, average='macro', zero_division=0)
        weighted_f1 = f1_score(y_val, y_pred, average='weighted', zero_division=0)
        
        fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
        fnr = fn / (fn + tp) if (fn + tp) > 0 else 0.0
        
        print(f"Results for {name}:")
        print(f"Accuracy: {acc:.4f} | Macro F1: {macro_f1:.4f} | Weighted F1: {weighted_f1:.4f}")
        print(f"Spam -> Precision: {spam_precision:.4f} | Recall: {spam_recall:.4f} | F1: {spam_f1:.4f}")
        print(f"Ham  -> Precision: {ham_precision:.4f} | Recall: {ham_recall:.4f} | F1: {ham_f1:.4f}")
        print(f"FPR: {fpr:.4f} | FNR: {fnr:.4f}")
        print(f"Confusion Matrix:\n[[{tn}, {fp}],\n [{fn}, {tp}]]")
        
        results.append({
            'Model': name,
            'Pipeline': pipeline,
            'Accuracy': acc,
            'Spam_Precision': spam_precision,
            'Spam_Recall': spam_recall,
            'Spam_F1': spam_f1,
            'Ham_Precision': ham_precision,
            'Ham_Recall': ham_recall,
            'Macro_F1': macro_f1,
            'Weighted_F1': weighted_f1,
            'FPR': fpr,
            'FNR': fnr,
            'TN': int(tn),
            'FP': int(fp),
            'FN': int(fn),
            'TP': int(tp)
        })
        
    print("\n--- Model Comparison ---")
    results_df = pd.DataFrame([ {k: v for k, v in r.items() if k != 'Pipeline'} for r in results ])
    print(results_df[['Model', 'Accuracy', 'Spam_Precision', 'Spam_Recall', 'Spam_F1', 'FPR', 'FNR']].to_string(index=False))
    
    # Model Selection Logic
    # Goal: Maximize Spam Recall and Spam Precision, while keeping FPR strictly extremely low.
    # Linear SVM often balances these well. Let's find the model with best Spam F1 but FPR < 0.01
    
    candidates = [r for r in results if r['FPR'] <= 0.01]
    if not candidates:
        # Fallback if none meet strict FPR
        candidates = results
    
    # Select the best one based on Spam F1
    best_result = sorted(candidates, key=lambda x: x['Spam_F1'], reverse=True)[0]
    best_model_name = best_result['Model']
    best_pipeline = best_result['Pipeline']
    
    print(f"\nSelected Best Model: {best_model_name}")
    print("Rationale: High Spam F1 score while maintaining a very low False Positive Rate (FPR), minimizing the chance of classifying legitimate emails as spam.")
    
    # Save the best model and metadata
    model_dir = os.path.join(os.path.dirname(__file__), '..', 'models')
    os.makedirs(model_dir, exist_ok=True)
    
    model_path = os.path.join(model_dir, 'spam_model_v1.joblib')
    joblib.dump(best_pipeline, model_path)
    print(f"\nBest model saved to {model_path}")
    
    # Save metadata
    metadata = {
        "version": "v1",
        "algorithm": best_model_name,
        "feature_configuration": {
            "word_tfidf": "Unigram, Bigram, Trigram (ngram_range=(1,3), min_df=2, max_df=0.95)",
            "char_tfidf": "Character 2-gram to 5-gram (analyzer='char_wb', ngram_range=(2,5), min_df=2, max_df=0.95)"
        },
        "evaluation_metrics": {
            k: v for k, v in best_result.items() if k != 'Pipeline' and k != 'Model'
        },
        "training_timestamp": datetime.now().isoformat(),
        "dataset_information": {
            "source": "spam.csv",
            "total_samples": len(data),
            "class_distribution_overall": class_dist,
            "train_size": len(X_train),
            "test_size": len(X_val),
            "class_distribution_val": val_class_dist
        },
        "model_selection_rationale": "Selected to maximize Spam F1 while keeping False Positive Rate (FPR) extremely low. High precision on Ham is essential so legitimate emails are not lost."
    }
    
    metadata_path = os.path.join(model_dir, 'metadata_v1.json')
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=4)
    print(f"Metadata saved to {metadata_path}")

if __name__ == '__main__':
    main()
