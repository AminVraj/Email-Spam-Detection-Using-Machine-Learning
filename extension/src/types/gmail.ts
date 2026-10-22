export interface GmailMessage {
  id: string;
  threadId: string;
  labelIds: string[];
  snippet: string;
  payload: {
    partId: string;
    mimeType: string;
    filename: string;
    headers: { name: string; value: string }[];
    body: {
      size: number;
      data?: string;
    };
    parts?: any[];
  };
  sizeEstimate: number;
  historyId: string;
  internalDate: string;
}

export interface GmailThread {
  id: string;
  snippet: string;
  historyId: string;
  messages: GmailMessage[];
}
