export interface GmailEmail {
  id: string;
  threadId: string;
  subject: string;
  sender: string;
  body: string;
  snippet: string;
  receivedAt: string;
  category: string;
  labelIds?: string[];
}

interface GmailMessageListResponse {
  messages?: {
    id: string;
    threadId: string;
  }[];
  nextPageToken?: string;
  resultSizeEstimate?: number;
}

interface GmailMessageResponse {
  id: string;
  threadId: string;
  labelIds?: string[];
  internalDate?: string;
  snippet?: string;
  payload?: GmailPayload;
}

interface GmailPayload {
  mimeType?: string;
  filename?: string;
  headers?: GmailHeader[];
  body?: {
    size?: number;
    data?: string;
  };
  parts?: GmailPayload[];
}

interface GmailHeader {
  name: string;
  value: string;
}

export class GmailApiService {
  private token: string;

  constructor(token: string) {
    this.token = token;
  }

  private async fetchApi<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const response = await fetch(
      `https://gmail.googleapis.com/gmail/v1/users/me/${endpoint}`,
      {
        ...options,
        headers: {
          ...options.headers,
          Authorization: `Bearer ${this.token}`,
          "Content-Type": "application/json"
        }
      }
    );

    const responseText = await response.text();

    if (!response.ok) {
      let message =
        `Gmail API error: ${response.status} ${response.statusText}`;

      try {
        const errorData = JSON.parse(responseText);

        if (errorData?.error?.message) {
          message = errorData.error.message;
        }
      } catch {
        if (responseText) {
          message = responseText;
        }
      }

      throw new Error(message);
    }

    try {
      return JSON.parse(responseText) as T;
    } catch {
      throw new Error(
        "Invalid response received from Gmail API."
      );
    }
  }

  async getProfile(): Promise<{
    emailAddress: string;
    messagesTotal: number;
    threadsTotal: number;
  }> {
    return this.fetchApi("profile");
  }

  async listMessages(
    maxResults = 20,
    query = "in:anywhere"
  ): Promise<GmailMessageListResponse> {
    const params = new URLSearchParams();

    params.set(
      "maxResults",
      String(maxResults)
    );

    if (query) {
      params.set("q", query);
    }

    return this.fetchApi<GmailMessageListResponse>(
      `messages?${params.toString()}`
    );
  }

  async getMessage(
    messageId: string
  ): Promise<GmailMessageResponse> {
    return this.fetchApi<GmailMessageResponse>(
      `messages/${encodeURIComponent(messageId)}?format=full`
    );
  }

  async getEmails(
    maxResults = 20
  ): Promise<GmailEmail[]> {
    console.log(
      `[GMAIL] Fetching up to ${maxResults} Gmail messages...`
    );

    const listResponse =
      await this.listMessages(
        maxResults,
        "in:anywhere"
      );

    const messageRefs =
      listResponse.messages || [];

    console.log(
      `[GMAIL] Found ${messageRefs.length} messages.`
    );

    const emails: GmailEmail[] = [];

    for (const messageRef of messageRefs) {
      try {
        const message =
          await this.getMessage(
            messageRef.id
          );

        const subject =
          this.getHeader(
            message.payload,
            "Subject"
          ) || "(No subject)";

        const sender =
          this.getHeader(
            message.payload,
            "From"
          ) || "(Unknown sender)";

        const body =
          this.extractBody(
            message.payload
          );

        const receivedAt =
          message.internalDate
            ? new Date(
                Number(
                  message.internalDate
                )
              ).toISOString()
            : "";

        const labelIds = message.labelIds || [];
        const category = this.extractCategory(labelIds);

        emails.push({
          id: message.id,
          threadId: message.threadId,
          subject,
          sender,
          body,
          snippet:
            message.snippet || "",
          receivedAt,
          category,
          labelIds
        });
      } catch (error) {
        console.error(
          `[GMAIL] Failed to process message ${messageRef.id}:`,
          error
        );
      }
    }

    console.log(
      `[GMAIL] Successfully parsed ${emails.length} emails.`
    );

    return emails;
  }

  extractCategory(labelIds: string[] = []): string {
    const set = new Set(labelIds);
    if (set.has("CATEGORY_PROMOTIONS")) {
      return "PROMOTIONS";
    }
    if (set.has("CATEGORY_SOCIAL")) {
      return "SOCIAL";
    }
    if (set.has("CATEGORY_UPDATES")) {
      return "UPDATES";
    }
    if (set.has("CATEGORY_FORUMS")) {
      return "FORUMS";
    }
    return "PRIMARY";
  }

  private getHeader(
    payload:
      | GmailPayload
      | undefined,
    headerName: string
  ): string {
    if (!payload?.headers) {
      return "";
    }

    const header =
      payload.headers.find(
        (item) =>
          item.name.toLowerCase() ===
          headerName.toLowerCase()
      );

    return header?.value || "";
  }

  private extractBody(
    payload:
      | GmailPayload
      | undefined
  ): string {
    if (!payload) {
      return "";
    }

    const plainText =
      this.findMimePart(
        payload,
        "text/plain"
      );

    if (plainText) {
      return plainText;
    }

    const html =
      this.findMimePart(
        payload,
        "text/html"
      );

    if (html) {
      return this.stripHtml(html);
    }

    if (payload.body?.data) {
      return this.decodeBase64Url(
        payload.body.data
      );
    }

    return "";
  }

  private findMimePart(
    payload: GmailPayload,
    mimeType: string
  ): string | null {
    if (
      payload.mimeType?.toLowerCase() ===
        mimeType.toLowerCase() &&
      payload.body?.data
    ) {
      return this.decodeBase64Url(
        payload.body.data
      );
    }

    if (payload.parts) {
      for (const part of payload.parts) {
        const result =
          this.findMimePart(
            part,
            mimeType
          );

        if (result) {
          return result;
        }
      }
    }

    return null;
  }

  private decodeBase64Url(
    data: string
  ): string {
    try {
      const base64 =
        data
          .replace(/-/g, "+")
          .replace(/_/g, "/");

      const padded =
        base64 +
        "=".repeat(
          (4 -
            (base64.length % 4)) %
            4
        );

      const binary =
        atob(padded);

      const bytes =
        Uint8Array.from(
          binary,
          (char) =>
            char.charCodeAt(0)
        );

      return new TextDecoder(
        "utf-8"
      ).decode(bytes);
    } catch (error) {
      console.error(
        "[GMAIL] Base64 decoding failed:",
        error
      );

      return "";
    }
  }

  private stripHtml(
    html: string
  ): string {
    return html
      .replace(
        /<script[\s\S]*?<\/script>/gi,
        " "
      )
      .replace(
        /<style[\s\S]*?<\/style>/gi,
        " "
      )
      .replace(
        /<[^>]*>/g,
        " "
      )
      .replace(
        /&nbsp;/gi,
        " "
      )
      .replace(
        /&amp;/gi,
        "&"
      )
      .replace(
        /&lt;/gi,
        "<"
      )
      .replace(
        /&gt;/gi,
        ">"
      )
      .replace(
        /&quot;/gi,
        '"'
      )
      .replace(
        /&#39;/gi,
        "'"
      )
      .replace(
        /\s+/g,
        " "
      )
      .trim();
  }
}
