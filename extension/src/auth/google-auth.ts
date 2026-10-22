const GOOGLE_CLIENT_ID = "1044023892905-910jptpfgub2ag6am67ocpgukhcnrgd1.apps.googleusercontent.com";
const SCOPES = [
  "https://www.googleapis.com/auth/gmail.readonly",
  "https://www.googleapis.com/auth/userinfo.email"
].join(" ");

let _activeToken: string | null = null;

export async function launchWebAuthFlowAccountSelection(): Promise<string> {
  return new Promise((resolve, reject) => {
    if (!chrome.identity || typeof chrome.identity.launchWebAuthFlow !== "function") {
      return reject(new Error("launchWebAuthFlow is not available in this environment."));
    }

    const redirectUri = chrome.identity.getRedirectURL
      ? chrome.identity.getRedirectURL()
      : `https://${chrome.runtime?.id || "extension"}.chromiumapp.org/`;

    const state = Math.random().toString(36).substring(2) + Date.now().toString(36);

    const authUrl = new URL("https://accounts.google.com/o/oauth2/v2/auth");
    authUrl.searchParams.set("client_id", GOOGLE_CLIENT_ID);
    authUrl.searchParams.set("response_type", "token");
    authUrl.searchParams.set("redirect_uri", redirectUri);
    authUrl.searchParams.set("scope", SCOPES);
    authUrl.searchParams.set("prompt", "select_account");
    authUrl.searchParams.set("state", state);

    chrome.identity.launchWebAuthFlow(
      {
        url: authUrl.toString(),
        interactive: true
      },
      (redirectUrl) => {
        const error = chrome.runtime.lastError;
        if (error) {
          return reject(
            new Error(error.message || "Google OAuth flow was cancelled or failed.")
          );
        }
        if (!redirectUrl) {
          return reject(new Error("No redirect URL received from Google OAuth flow."));
        }

        try {
          const parsedUrl = new URL(redirectUrl);
          const hash = parsedUrl.hash.startsWith("#") ? parsedUrl.hash.substring(1) : parsedUrl.hash;
          const params = new URLSearchParams(hash || parsedUrl.search);

          const returnedState = params.get("state");
          if (returnedState && returnedState !== state) {
            return reject(new Error("OAuth state validation mismatch."));
          }

          const accessToken = params.get("access_token");
          if (!accessToken) {
            const errParam = params.get("error");
            const errDesc = params.get("error_description");
            return reject(new Error(errDesc || errParam || "Failed to extract access token from OAuth response."));
          }

          _activeToken = accessToken;
          resolve(accessToken);
        } catch (parseErr) {
          reject(new Error("Failed to parse OAuth redirect URL: " + String(parseErr)));
        }
      }
    );
  });
}

export async function signIn(): Promise<string> {
  // First attempt launchWebAuthFlow with prompt=select_account for intentional account picking
  try {
    return await launchWebAuthFlowAccountSelection();
  } catch (err: any) {
    const msg = (err?.message || "").toLowerCase();
    // If the user cancelled or denied consent, reject immediately without unwanted auto-fallback
    if (msg.includes("denied") || msg.includes("cancelled") || msg.includes("canceled") || msg.includes("close")) {
      throw err;
    }
    // Fallback to chrome.identity.getAuthToken if launchWebAuthFlow is unavailable or redirect URI not configured
    return new Promise((resolve, reject) => {
      chrome.identity.getAuthToken({ interactive: true }, (token) => {
        const error = chrome.runtime.lastError;
        if (error) {
          return reject(
            new Error(
              error.message || "Google authentication was cancelled or failed."
            )
          );
        }
        if (!token) {
          return reject(new Error("No token received."));
        }
        _activeToken = token;
        resolve(token);
      });
    });
  }
}

export async function getAccessToken(): Promise<string> {
  if (_activeToken) {
    return _activeToken;
  }
  return new Promise((resolve, reject) => {
    chrome.identity.getAuthToken({ interactive: false }, (token) => {
      const error = chrome.runtime.lastError;
      if (error) {
        return reject(
          new Error(error.message || "Not authenticated.")
        );
      }
      if (!token) {
        return reject(new Error("No token received."));
      }
      _activeToken = token;
      resolve(token);
    });
  });
}

export async function signOut(): Promise<void> {
  const tokenToRevoke = _activeToken;
  _activeToken = null;

  let cachedToken: string | null = null;
  try {
    cachedToken = await new Promise<string | null>((resolve) => {
      chrome.identity.getAuthToken({ interactive: false }, (tok) => {
        resolve(tok || null);
      });
    });
  } catch {
    cachedToken = null;
  }

  const token = tokenToRevoke || cachedToken;
  if (token) {
    // 1. Revoke access token on Google OAuth servers
    try {
      await fetch(
        `https://oauth2.googleapis.com/revoke?token=${encodeURIComponent(token)}`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/x-www-form-urlencoded",
          },
        }
      );
    } catch (err) {
      console.warn("[AUTH] Server token revocation request failed:", err);
    }

    // 2. Remove token from Chrome identity token cache
    await new Promise<void>((resolve) => {
      chrome.identity.removeCachedAuthToken({ token }, () => {
        const _err = chrome.runtime.lastError;
        resolve();
      });
    });
  }

  // 3. Clear all cached auth tokens to reset Chrome's account preference
  await new Promise<void>((resolve) => {
    if (
      chrome.identity &&
      typeof chrome.identity.clearAllCachedAuthTokens === "function"
    ) {
      chrome.identity.clearAllCachedAuthTokens(() => {
        const _err = chrome.runtime.lastError;
        resolve();
      });
    } else {
      resolve();
    }
  });
}

export async function isAuthenticated(): Promise<boolean> {
  try {
    const token = await getAccessToken();
    await getCurrentUser(token);
    return true;
  } catch {
    return false;
  }
}

export async function getCurrentUser(
  token: string
): Promise<{ email: string }> {
  const response = await fetch(
    "https://gmail.googleapis.com/gmail/v1/users/me/profile",
    {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    }
  );

  if (!response.ok) {
    throw new Error("Failed to fetch Gmail account profile.");
  }

  const data = await response.json();
  if (!data || !data.emailAddress) {
    throw new Error("Invalid profile response received from Gmail API.");
  }

  return { email: data.emailAddress };
}
