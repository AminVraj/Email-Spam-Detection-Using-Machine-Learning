import {
  signIn,
  signOut,
  isAuthenticated,
  getCurrentUser,
  getAccessToken,
} from "../auth/google-auth.js";

document.addEventListener(
  "DOMContentLoaded",
  async () => {
    const statusEl = document.getElementById(
      "account-status"
    ) as HTMLParagraphElement;

    const connectBtn = document.getElementById(
      "connect-btn"
    ) as HTMLButtonElement;

    const analyzeBtn = document.getElementById(
      "analyze-btn"
    ) as HTMLButtonElement;

    const disconnectBtn =
      document.getElementById(
        "disconnect-btn"
      ) as HTMLButtonElement;

    const errorEl = document.getElementById(
      "error-message"
    ) as HTMLParagraphElement;

    let resultsEl =
      document.getElementById(
        "analysis-results"
      ) as HTMLDivElement | null;

    // Create results container if it doesn't
    // already exist in popup.html.
    if (!resultsEl) {
      resultsEl = document.createElement("div");
      resultsEl.id = "analysis-results";

      resultsEl.style.marginTop = "16px";
      resultsEl.style.padding = "12px";
      resultsEl.style.borderRadius = "8px";
      resultsEl.style.background = "#f5f7fa";
      resultsEl.style.display = "none";

      analyzeBtn.parentElement?.appendChild(
        resultsEl
      );
    }

    function showError(
      message: string
    ): void {
      console.error(
        "Extension error:",
        message
      );

      errorEl.textContent = message;
      errorEl.classList.remove("hidden");
    }

    function hideError(): void {
      errorEl.textContent = "";
      errorEl.classList.add("hidden");
    }

    function setDisconnectedUI(): void {
      statusEl.textContent = "Not connected";
      statusEl.classList.remove(
        "connected"
      );

      connectBtn.classList.remove(
        "hidden"
      );

      analyzeBtn.classList.add(
        "hidden"
      );

      disconnectBtn.classList.add(
        "hidden"
      );
    }

    function setConnectedUI(
      email: string
    ): void {
      statusEl.textContent =
        `Connected\n${email}`;

      statusEl.classList.add(
        "connected"
      );

      connectBtn.classList.add(
        "hidden"
      );

      analyzeBtn.classList.remove(
        "hidden"
      );

            analyzeBtn.disabled = false;

      disconnectBtn.classList.remove(
        "hidden"
      );
    }

    function showAnalysisResults(
      response: any
    ): void {
      if (!resultsEl) {
        return;
      }

      resultsEl.style.display = "block";
      resultsEl.replaceChildren();

      const titleEl = document.createElement("div");
      titleEl.style.fontWeight = "600";
      titleEl.style.marginBottom = "8px";
      titleEl.textContent = "Analysis Complete";

      const totalEl = document.createElement("div");
      totalEl.style.fontSize = "14px";
      totalEl.style.marginBottom = "4px";
      const totalLabel = document.createTextNode("Emails analyzed: ");
      const totalVal = document.createElement("strong");
      totalVal.textContent = String(response.total ?? 0);
      totalEl.appendChild(totalLabel);
      totalEl.appendChild(totalVal);

      const spamEl = document.createElement("div");
      spamEl.style.fontSize = "14px";
      spamEl.style.marginBottom = "4px";
      spamEl.style.color = "#dc2626";
      const spamLabel = document.createTextNode("Spam: ");
      const spamVal = document.createElement("strong");
      spamVal.textContent = String(response.spam ?? 0);
      spamEl.appendChild(spamLabel);
      spamEl.appendChild(spamVal);

      const hamEl = document.createElement("div");
      hamEl.style.fontSize = "14px";
      hamEl.style.color = "#16a34a";
      const hamLabel = document.createTextNode("Ham: ");
      const hamVal = document.createElement("strong");
      hamVal.textContent = String(response.ham ?? 0);
      hamEl.appendChild(hamLabel);
      hamEl.appendChild(hamVal);

      resultsEl.appendChild(titleEl);
      resultsEl.appendChild(totalEl);
      resultsEl.appendChild(spamEl);
      resultsEl.appendChild(hamEl);
    }

    async function updateUI(): Promise<void> {
      hideError();

      try {
        console.log(
          "Checking Gmail authentication..."
        );

        const authenticated =
          await isAuthenticated();

        if (!authenticated) {
          setDisconnectedUI();
          return;
        }

        const token =
          await getAccessToken();

        const user =
          await getCurrentUser(
            token
          );

        setConnectedUI(
          user.email
        );
      } catch (
      error: unknown
      ) {
        console.error(
          "UI update error:",
          error
        );

        setDisconnectedUI();

        const message =
          error instanceof Error
            ? error.message
            : String(error);

        showError(
          message ||
          "Failed to load Gmail account."
        );
      }
    }

    connectBtn.addEventListener(
      "click",
      async () => {
        hideError();

        try {
          connectBtn.textContent =
            "Connecting...";

          connectBtn.disabled = true;

          const token =
            await signIn();

          const user =
            await getCurrentUser(
              token
            );

          setConnectedUI(
            user.email
          );
        } catch (
        error: unknown
        ) {
          console.error(
            "Gmail connection error:",
            error
          );

          setDisconnectedUI();

          const message =
            error instanceof Error
              ? error.message
              : String(error);

          showError(
            message ||
            "Failed to connect to Google."
          );
        } finally {
          connectBtn.textContent =
            "Connect Gmail";

          connectBtn.disabled = false;
        }
      }
    );

    disconnectBtn.addEventListener(
      "click",
      async () => {
        hideError();

        try {
          disconnectBtn.textContent =
            "Disconnecting...";

          disconnectBtn.disabled = true;

          await signOut();

          setDisconnectedUI();

          if (resultsEl) {
            resultsEl.style.display =
              "none";
          }
        } catch (
        error: unknown
        ) {
          const message =
            error instanceof Error
              ? error.message
              : String(error);

          showError(
            message ||
            "Failed to disconnect."
          );
        } finally {
          disconnectBtn.textContent =
            "Disconnect";

          disconnectBtn.disabled = false;
        }
      }
    );

    analyzeBtn.addEventListener(
      "click",
      () => {
        hideError();

        if (resultsEl) {
          resultsEl.style.display =
            "none";
        }

        analyzeBtn.textContent =
          "Analyzing Gmail...";

        analyzeBtn.disabled = true;

        console.log(
          "Starting Gmail analysis..."
        );

        chrome.runtime.sendMessage(
          {
            action:
              "analyze_gmail",
          },
          (response) => {
            const runtimeError =
              chrome.runtime.lastError;

            if (runtimeError) {
              console.error(
                "Background error:",
                runtimeError.message
              );

              showError(
                runtimeError.message ||
                "Background service error."
              );

              analyzeBtn.textContent =
                "Analyze Gmail";

              analyzeBtn.disabled =
                false;

              return;
            }

            if (!response) {
              showError(
                "No response received from the background service."
              );

              analyzeBtn.textContent =
                "Analyze Gmail";

              analyzeBtn.disabled =
                false;

              return;
            }

            if (
              response.status ===
              "error"
            ) {
              showError(
                response.error ||
                "Gmail analysis failed."
              );

              analyzeBtn.textContent =
                "Analyze Gmail";

              analyzeBtn.disabled =
                false;

              return;
            }

            console.log(
              "Gmail analysis result:",
              response
            );

            showAnalysisResults(
              response
            );

            analyzeBtn.textContent =
              "Analyze Gmail";

            analyzeBtn.disabled =
              false;
          }
        );
      }
    );

    await updateUI();
  }
);
