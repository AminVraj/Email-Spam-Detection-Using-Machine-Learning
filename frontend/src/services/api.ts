import type {
  Email,
  Statistics,
  FeedbackQualityReport,
  ModelVersion,
  ModelComparison,
  GmailSyncResult,
  Prediction
} from "../types";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

async function fetcher<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${url}`, {
    credentials: "include",
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });
  if (!res.ok) {
    let message = "An error occurred";
    try {
      const err = await res.json();
      if (err.blocked) {
        throw err;
      }
      message = err.detail || message;
    } catch (e: any) {
      if (e.blocked) throw e;
      // Ignore JSON parse error
    }
    throw new Error(message);
  }
  return res.json();
}

export const api = {
  getHealth: () => fetcher<{ status: string }>("/health"),

  getAuthMe: () => fetcher<{ email: string; is_admin: boolean; auth_method: string }>("/auth/me"),

  createSession: (token: string) =>
    fetcher<{ status: string; email: string; is_admin: boolean }>("/auth/session", {
      method: "POST",
      body: JSON.stringify({ token }),
    }),

  logout: () => fetcher<{ status: string }>("/auth/logout", { method: "POST" }),

  getStatistics: () => fetcher<Statistics>("/statistics"),

  getGmailAuthStatus: () => fetcher<{ authenticated: boolean }>("/gmail/auth/status"),

  syncGmail: () => fetcher<GmailSyncResult>("/gmail/sync", { method: "POST" }),

  getEmails: () => fetcher<{ emails: Email[] }>("/emails?limit=100"),

  getEmailDetails: (id: number) => fetcher<Email>(`/emails/${id}`),

  submitFeedback: (emailId: number, label: "SPAM" | "HAM") =>
    fetcher("/feedback", {
      method: "POST",
      body: JSON.stringify({ email_id: emailId, user_label: label }),
    }),

  getFeedbackQuality: () => fetcher<FeedbackQualityReport>("/feedback/quality-report"),

  getModels: () => fetcher<{ models: ModelVersion[] }>("/models"),

  trainCandidate: () => fetcher<{ status: string; version: string }>("/models/train-candidate", { method: "POST" }),

  compareModel: (version: string) => fetcher<ModelComparison>(`/models/compare/${version}`),

  promoteModel: (version: string) => fetcher(`/models/${version}/promote`, { method: "POST" }),

  rollbackModel: (version: string) => fetcher(`/models/${version}/rollback`, { method: "POST" }),

  analyzeOCR: async (file: File) => {
    const formData = new FormData();
    formData.append("file", file);
    const res = await fetch(`${API_BASE}/ocr`, {
      method: "POST",
      credentials: "include",
      body: formData,
    });
    if (!res.ok) {
      let message = "OCR failed";
      try {
        const err = await res.json();
        if (err.blocked) {
          throw err;
        }
        message = err.detail || message;
      } catch (e: any) {
        if (e.blocked) throw e;
      }
      throw new Error(message);
    }
    return res.json() as Promise<{text: string}>;
  },

  analyzeManual: (subject: string, body: string, sender?: string) =>
    fetcher<Prediction>("/analyze-manual", {
      method: "POST",
      body: JSON.stringify({ subject, body, sender: sender || "" })
    }),
};
