# Email Sentinel AI - Chrome Extension

This Chrome Extension serves as a secure bridge between your Gmail account and the Email Sentinel AI backend. It uses OAuth 2.0 via `chrome.identity` to request read-only access to your emails without ever handling or storing your Gmail password.

## Intended Architecture

The final architecture for the extension will work as follows:

```text
                    CHROME EXTENSION
                           |
                           v
                    Google OAuth 2.0
                           |
                           v
                    Authorized Gmail
                           |
                           v
                       Gmail API
                           |
                           v
                  Email retrieval
                           |
                           v
                    Normalization
                           |
                ┌──────────┴──────────┐
                |                     |
         Gmail category          Email content
                |                     |
                v                     v
        PROMOTIONS?             ML classifier
                |                     |
                v                ┌────┴────┐
           PROMOTION             SPAM     HAM
```

The extension securely passes data to the existing FastAPI backend for Machine Learning classification (TF-IDF + LinearSVC).

## Setup & Development

### 1. Build the extension

```bash
npm install
npm run build
```

This will compile the TypeScript source into the `dist/` directory.

### 2. Google Cloud Configuration

Before the extension can authenticate users, a Google Cloud OAuth Client must be created:
1. Navigate to Google Cloud Console.
2. Enable the **Gmail API**.
3. Create an **OAuth 2.0 Client ID** (Type: Chrome Extension).
4. You will be provided with a Client ID string.
5. Copy the Client ID and paste it into `manifest.json` replacing `"YOUR_GOOGLE_OAUTH_CLIENT_ID"`.

### 3. Loading the Extension in Chrome

1. Open Chrome and go to `chrome://extensions`.
2. Enable **Developer Mode** in the top right.
3. Click **Load unpacked** and select the `extension/dist` directory.
4. The extension is now loaded and ready for testing.
