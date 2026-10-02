import os
import json
import pandas as pd
from typing import List, Dict, Any, Tuple
from sklearn.model_selection import train_test_split
from backend.config import DATASETS_DIR, TRAINING_DIR
from backend.nlp.preprocessing import clean_text

def load_base_dataset(csv_path: str = None) -> pd.DataFrame:
    """
    Loads and standardizes the base training dataset (spam.csv).
    Does NOT modify the original file.
    """
    if csv_path is None:
        csv_path = os.path.join(DATASETS_DIR, "spam.csv")
        
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Base dataset not found at {csv_path}")
        
    df = pd.read_csv(csv_path)
    
    # Map Category ('ham'/'spam') to standard 'HAM'/'SPAM'
    if 'Category' in df.columns and 'Message' in df.columns:
        df['text'] = df['Message'].astype(str)
        df['label'] = df['Category'].apply(lambda x: 'SPAM' if str(x).lower() == 'spam' else 'HAM')
    elif 'text' in df.columns and 'label' in df.columns:
        df['label'] = df['label'].apply(lambda x: 'SPAM' if str(x).upper() == 'SPAM' else 'HAM')
    else:
        raise ValueError("Invalid base dataset format")
        
    df['source'] = 'original_dataset'
    df['email_id'] = None
    df['model_version'] = 'v1'
    
    return df[['text', 'label', 'source', 'email_id', 'model_version']]

def build_combined_dataset(validated_feedback: List[Dict[str, Any]], 
                           output_dir: str = None, 
                           base_csv_path: str = None) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Constructs the combined training dataset from original base dataset and validated feedback.
    Saves:
    - base_dataset.csv
    - validated_feedback_dataset.json
    - combined_training_dataset.csv
    """
    if output_dir is None:
        output_dir = TRAINING_DIR
    os.makedirs(output_dir, exist_ok=True)
    
    # 1. Load base dataset
    base_df = load_base_dataset(base_csv_path)
    base_df.to_csv(os.path.join(output_dir, "base_dataset.csv"), index=False)
    
    # 2. Format validated feedback
    feedback_records = []
    for fb in validated_feedback:
        feedback_records.append({
            "text": fb["text"],
            "label": fb["label"].upper(),
            "source": "user_feedback",
            "email_id": fb.get("email_id"),
            "model_version": fb.get("model_version", "v1")
        })
        
    # Save validated feedback JSON
    feedback_json_path = os.path.join(output_dir, "validated_feedback_dataset.json")
    with open(feedback_json_path, 'w') as f:
        json.dump(feedback_records, f, indent=4)
        
    fb_df = pd.DataFrame(feedback_records) if feedback_records else pd.DataFrame(columns=['text', 'label', 'source', 'email_id', 'model_version'])
    
    # 3. Combine base dataset and feedback
    if not fb_df.empty:
        combined_df = pd.concat([base_df, fb_df], ignore_index=True)
    else:
        combined_df = base_df.copy()
        
    combined_csv_path = os.path.join(output_dir, "combined_training_dataset.csv")
    combined_df.to_csv(combined_csv_path, index=False)
    
    summary = {
        "total_records": len(combined_df),
        "base_dataset_records": len(base_df),
        "user_feedback_records": len(fb_df),
        "class_distribution": combined_df['label'].value_counts().to_dict()
    }
    
    return combined_df, summary

def split_training_data_leakproof(df: pd.DataFrame, 
                                  test_size: float = 0.2, 
                                  random_state: int = 42) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Splits combined training dataset into train and test sets while preventing data leakage.
    Ensures that identical text strings (after cleaning) do not appear in both train and test sets.
    """
    df = df.copy()
    df['clean_text'] = df['text'].apply(clean_text)
    
    # Group by clean text to find unique texts and their majority label
    unique_texts = df.groupby('clean_text').agg({
        'label': lambda x: x.mode()[0] if not x.empty else 'HAM'
    }).reset_index()
    
    # Perform stratified split on unique texts
    train_texts, test_texts = train_test_split(
        unique_texts,
        test_size=test_size,
        random_state=random_state,
        stratify=unique_texts['label']
    )
    
    train_set_clean = set(train_texts['clean_text'])
    test_set_clean = set(test_texts['clean_text'])
    
    # Assign records based on clean text split
    train_df = df[df['clean_text'].isin(train_set_clean)].copy()
    test_df = df[df['clean_text'].isin(test_set_clean)].copy()
    
    # Verify zero text overlap between train and test
    overlap = set(train_df['clean_text']).intersection(set(test_df['clean_text']))
    if overlap:
        raise ValueError(f"Data leakage detected: {len(overlap)} texts overlapped between train and test sets.")
        
    train_df = train_df.drop(columns=['clean_text'])
    test_df = test_df.drop(columns=['clean_text'])
    
    return train_df, test_df
