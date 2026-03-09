/**
 * AI Advisor API client.
 *
 * Handles conversation management, message sending (including SSE streaming),
 * quick analysis, and scenario analysis.
 */

import { httpClient } from "./client";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface StartConversationRequest {
  profile_id?: string | null;
  language?: string;
  message?: string | null;
}

export interface SendMessageRequest {
  message: string;
}

export interface ConversationResponse {
  conversation_id: string;
  message: string;
  intent?: string | null;
  profile_id?: string | null;
  has_context: boolean;
}

export interface MessageDTO {
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: number;
  metadata?: Record<string, unknown>;
}

export interface ConversationDetail {
  conversation_id: string;
  profile_id?: string | null;
  language: string;
  message_count: number;
  created_at: number;
  updated_at: number;
  messages: MessageDTO[];
}

export interface ConversationListItem {
  conversation_id: string;
  profile_id?: string | null;
  message_count: number;
  language: string;
  created_at: number;
  updated_at: number;
  last_message?: string | null;
}

export interface QuickAnalysisResponse {
  profile_id: string;
  analysis: string;
  has_context: boolean;
  success: boolean;
}

export interface ScenarioAnalysisResponse {
  profile_id: string;
  scenario: string;
  analysis: string;
  has_context: boolean;
}

// ---------------------------------------------------------------------------
// API Methods
// ---------------------------------------------------------------------------

const BASE = "/api/v1/ai-advisor";

export const aiAdvisorApi = {
  /**
   * Start a new conversation. Optionally pre-load a borrower profile
   * and/or send an initial message.
   */
  async startConversation(
    req: StartConversationRequest
  ): Promise<ConversationResponse> {
    const { data } = await httpClient.post(`${BASE}/conversations`, req);
    return data;
  },

  /**
   * Send a message in an existing conversation (non-streaming).
   */
  async sendMessage(
    conversationId: string,
    req: SendMessageRequest
  ): Promise<ConversationResponse> {
    const { data } = await httpClient.post(
      `${BASE}/conversations/${conversationId}/messages`,
      req
    );
    return data;
  },

  /**
   * Send a message and stream the response using Server-Sent Events.
   *
   * Returns a callback to abort the stream.
   */
  streamMessage(
    conversationId: string,
    message: string,
    onToken: (token: string) => void,
    onDone: () => void,
    onError?: (error: string) => void
  ): () => void {
    const controller = new AbortController();

    const url = `${BASE}/conversations/${conversationId}/messages/stream`;

    // Use fetch for SSE since Axios doesn't support streaming well
    fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message }),
      signal: controller.signal,
    })
      .then(async (response) => {
        if (!response.ok) {
          onError?.(`HTTP ${response.status}`);
          return;
        }

        const reader = response.body?.getReader();
        if (!reader) {
          onError?.("No response body");
          return;
        }

        const decoder = new TextDecoder();
        let buffer = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          buffer += decoder.decode(value, { stream: true });

          // Parse SSE events from buffer
          const lines = buffer.split("\n");
          buffer = lines.pop() || "";

          for (const line of lines) {
            if (line.startsWith("data: ")) {
              const data = line.slice(6);
              if (data === "[DONE]") {
                onDone();
                return;
              }
              if (data.startsWith("[ERROR]")) {
                onError?.(data);
                return;
              }
              onToken(data);
            }
          }
        }

        onDone();
      })
      .catch((err) => {
        if (err.name !== "AbortError") {
          onError?.(err.message);
        }
      });

    return () => controller.abort();
  },

  /**
   * Get full conversation history.
   */
  async getConversation(
    conversationId: string
  ): Promise<ConversationDetail> {
    const { data } = await httpClient.get(
      `${BASE}/conversations/${conversationId}`
    );
    return data;
  },

  /**
   * List conversations for a borrower profile.
   */
  async getProfileConversations(
    profileId: string,
    limit: number = 10
  ): Promise<ConversationListItem[]> {
    const { data } = await httpClient.get(
      `${BASE}/conversations/profile/${profileId}`,
      { params: { limit } }
    );
    return data.conversations;
  },

  /**
   * One-shot AI analysis for a borrower (no conversation created).
   */
  async quickAnalysis(
    profileId: string
  ): Promise<QuickAnalysisResponse> {
    const { data } = await httpClient.post(`${BASE}/analyze`, {
      profile_id: profileId,
    });
    return data;
  },

  /**
   * AI-powered what-if scenario analysis.
   */
  async scenarioAnalysis(
    profileId: string,
    scenario: string
  ): Promise<ScenarioAnalysisResponse> {
    const { data } = await httpClient.post(`${BASE}/scenarios`, {
      profile_id: profileId,
      scenario,
    });
    return data;
  },
};
