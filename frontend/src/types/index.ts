export interface Email {
  id: number;
  sender: string;
  subject: string;
  body?: string;
  received_at: string;
  classification: string;
  decision_score: number;
  model_version: string;
  feedback?: {
    user_label: string;
    original_prediction: string;
  };
}

export interface Prediction {
  classification: string;
  model_version: string;
  decision_score: number;
  email_id?: number;
}

export interface Statistics {
  total_predictions: number;
  spam_predictions: number;
  ham_predictions: number;
  total_feedback: number;
  user_corrections: number;
  predicted_spam_confirmed_by_user: number;
  predicted_ham_confirmed_by_user: number;
  user_feedback_observed_outcomes: {
    description: string;
    true_positives: number;
    true_negatives: number;
    false_positives: number;
    false_negatives: number;
    corrections: number;
  };
  model_version: string;
}

export interface ModelVersion {
  version: string;
  algorithm: string;
  status: string;
  training_timestamp: string;
  feedback_count_used: number;
  metrics: Record<string, number>;
}

export interface FeedbackQualityReport {
  total_feedback: number;
  valid_feedback: number;
  invalid_feedback: number;
  duplicate_feedback: number;
  conflicting_feedback: number;
  new_feedback_available: number;
  minimum_required: number;
  training_ready: boolean;
}

export interface ModelComparison {
  production_version: string;
  candidate_version: string;
  comparison: {
    degradation: {
      Spam_Precision: number;
      Spam_Recall: number;
    };
    fpr: number;
    decision: "APPROVED" | "REJECTED";
    reasons: string[];
  };
}

export interface GmailSyncResult {
  status: string;
  messages_processed: number;
  new_spam: number;
  new_ham: number;
}
