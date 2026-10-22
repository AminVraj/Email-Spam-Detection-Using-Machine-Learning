import { getAccessToken } from "../auth/google-auth.js";
import {
  GmailApiService,
  GmailEmail,
} from "../services/gmail-api.js";

const BACKEND_URL = "http://127.0.0.1:8000";
// Dashboard URL constant for post-analysis redirect
const DASHBOARD_URL = "http://localhost:5173/inbox";

interface PredictionResponse {
  classification: string;
  model_version?: string;
  decision_score?: number;
}

interface AnalyzedEmail {
  id: string;
  subject: string;
  sender: string;
  classification: string;
  decision_score?: number;
  model_version?: string;
  receivedAt: string;
}

chrome.runtime.onInstalled.addListener(() => {
  console.log(
    "Email Sentinel AI Extension Installed."
  );
});

chrome.runtime.onMessage.addListener(
  (request, sender, sendResponse) => {
    if (request.action === "analyze_gmail") {
      analyzeGmail()
        .then((result) => {
          sendResponse({
            status: "success",
            ...result,
          });
        })
        .catch((error: unknown) => {
          console.error(
            "[ANALYZE] Gmail analysis failed:",
            error
          );

          sendResponse({
            status: "error",
            error:
              error instanceof Error
                ? error.message
                : String(error),
          });
        });

      return true;
    }

    return false;
  }
);

async function analyzeGmail() {
  console.log(
    "[ANALYZE] Starting Gmail analysis..."
  );

  // 1. Get OAuth access token.
  const token = await getAccessToken();

  console.log(
    "[ANALYZE] Gmail access token retrieved."
  );

  // 2. Create Gmail API service and verify profile identity.
  const gmail = new GmailApiService(token);
  const profile = await gmail.getProfile();
  const accountEmail = profile.emailAddress;

  console.log(
    `[ANALYZE] Authenticated profile verified: ${accountEmail}`
  );

  // Establish dashboard session cookie so the opened dashboard tab has verified session
  try {
    await fetch(`${BACKEND_URL}/auth/session`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ token }),
    });
    console.log(`[ANALYZE] Dashboard session established for ${accountEmail}`);
  } catch (sessErr) {
    console.warn("[ANALYZE] Could not create dashboard session cookie:", sessErr);
  }

  // 3. Fetch latest emails.
  const emails = await gmail.getEmails(20);

  if (emails.length === 0) {
    // Open dashboard even if no emails found
    try {
      await chrome.tabs.create({ url: DASHBOARD_URL, active: true });
    } catch (tabError) {
      console.error("[ANALYZE] Failed to open dashboard tab:", tabError);
    }
    return {
      total: 0,
      spam: 0,
      ham: 0,
      results: [],
      message: "No Gmail messages were found.",
    };
  }

  console.log(
    `[ANALYZE] Analyzing ${emails.length} emails for ${accountEmail}...`
  );

  const results: AnalyzedEmail[] = [];

  let spamCount = 0;
  let hamCount = 0;
  let errorCount = 0;
  let lastErrorMsg = "";

  // 4. Send each email to the existing ML backend.
  for (const email of emails) {
    try {
      const prediction =
        await predictEmail(email, token, accountEmail);

      const classification =
        normalizeClassification(
          prediction.classification
        );

      if (classification === "spam") {
        spamCount++;
      } else {
        hamCount++;
      }

      results.push({
        id: email.id,
        subject: email.subject,
        sender: email.sender,
        classification,
        decision_score:
          prediction.decision_score,
        model_version:
          prediction.model_version,
        receivedAt: email.receivedAt,
      });

      console.log(
        `[ANALYZE] ${email.subject} -> ${classification}`
      );
    } catch (error) {
      errorCount++;
      lastErrorMsg = error instanceof Error ? error.message : String(error);
      console.error(
        `[ANALYZE] Prediction failed for ${email.subject}:`,
        error
      );
    }
  }

  // If emails were found but none could be processed, fail analysis and do not redirect
  if (emails.length > 0 && results.length === 0) {
    throw new Error(
      `Analysis failed: Unable to process Gmail messages (${errorCount} error(s)). ${lastErrorMsg || "Backend service unreachable."}`
    );
  }

  console.log(
    `[ANALYZE] Complete. Spam=${spamCount}, Ham=${hamCount}`
  );

  // Open and activate the dashboard tab after successful analysis
  try {
    console.log(`[ANALYZE] Opening dashboard tab at ${DASHBOARD_URL}`);
    await chrome.tabs.create({ url: DASHBOARD_URL, active: true });
  } catch (tabError) {
    console.error("[ANALYZE] Failed to open dashboard tab:", tabError);
  }

  return {
    total: results.length,
    spam: spamCount,
    ham: hamCount,
    results,
    message: `Analyzed ${results.length} emails.`,
  };
}

async function predictEmail(
  email: GmailEmail,
  token: string,
  accountEmail?: string
): Promise<PredictionResponse> {
  const response = await fetch(
    `${BACKEND_URL}/predict`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${token}`,
      },
      body: JSON.stringify({
        subject: email.subject,
        body: email.body,
        sender: email.sender,
        provider: "gmail",
        provider_message_id: email.id,
        provider_category: (email as any).category || "PRIMARY",
        received_at: email.receivedAt,
        account_email: accountEmail,
      }),
    }
  );

  const responseText = await response.text();

  if (!response.ok) {
    let message = `ML backend error: ${response.status} ${response.statusText}`;

    try {
      const data = JSON.parse(responseText);

      if (data?.detail) {
        if (typeof data.detail === "string") {
          message = data.detail;
        } else {
          message = JSON.stringify(
            data.detail
          );
        }
      }

      if (data?.message) {
        message = data.message;
      }
    } catch {
      if (responseText) {
        message = responseText;
      }
    }

    throw new Error(message);
  }

  try {
    return JSON.parse(
      responseText
    ) as PredictionResponse;
  } catch {
    throw new Error(
      "ML backend returned an invalid JSON response."
    );
  }
}

function normalizeClassification(
  classification: string
): string {
  const value =
    classification.trim().toLowerCase();

  if (
    value === "spam" ||
    value === "1" ||
    value === "true"
  ) {
    return "spam";
  }

  return "ham";
}