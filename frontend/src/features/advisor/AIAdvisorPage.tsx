/**
 * AI Advisor Chat Page — full-page conversational interface.
 *
 * Features:
 * - Start new conversations with optional profile context
 * - Real-time streaming responses
 * - Message history with role-based styling
 * - Quick actions for common questions
 * - Profile linking for personalised advice
 */

import { useState, useRef, useEffect, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Send,
  Bot,
  User,
  Sparkles,
  MessageCircle,
  ArrowDown,
  Loader2,
  RefreshCw,
  ChevronDown,
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import { Button } from "@/components/ui/Button";
import { cn } from "@/lib/utils";
import { aiAdvisorApi, profileApi } from "@/api";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: number;
  intent?: string;
  isStreaming?: boolean;
}

// ---------------------------------------------------------------------------
// Quick Action Suggestions
// ---------------------------------------------------------------------------

const QUICK_ACTIONS = [
  { label: "Am I eligible for KCC?", icon: "🏦" },
  { label: "What's my risk level?", icon: "📊" },
  { label: "Best time to take a loan?", icon: "📅" },
  { label: "Explain my cash flow", icon: "💰" },
  { label: "What if monsoon is late?", icon: "🌧️" },
  { label: "How to reduce my risk?", icon: "🛡️" },
] as const;

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function AIAdvisorPage() {
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [profileId, setProfileId] = useState("");
  const [linkedProfile, setLinkedProfile] = useState<string | null>(null);
  const [showScrollButton, setShowScrollButton] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch all profiles for the dropdown
  const { data: profilesData, isLoading: profilesLoading } = useQuery({
    queryKey: ["profiles"],
    queryFn: () => profileApi.list({ limit: 200 }),
  });
  const profiles = profilesData?.items ?? [];

  // Find the display name for the currently linked profile
  const linkedProfileName = profiles.find(
    (p) => p.profile_id === linkedProfile
  )?.name;

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const abortRef = useRef<(() => void) | null>(null);

  // Auto-scroll to bottom
  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  // Detect if user has scrolled up
  useEffect(() => {
    const container = messagesContainerRef.current;
    if (!container) return;

    const handleScroll = () => {
      const { scrollTop, scrollHeight, clientHeight } = container;
      setShowScrollButton(scrollHeight - scrollTop - clientHeight > 100);
    };

    container.addEventListener("scroll", handleScroll);
    return () => container.removeEventListener("scroll", handleScroll);
  }, []);

  // ------------------------------------------------------------------
  // Start conversation
  // ------------------------------------------------------------------

  const startConversation = useCallback(
    async (initialMessage?: string) => {
      setIsLoading(true);
      setError(null);

      try {
        const resp = await aiAdvisorApi.startConversation({
          profile_id: linkedProfile || undefined,
          language: "en",
          message: initialMessage || undefined,
        });

        setConversationId(resp.conversation_id);

        const newMessages: ChatMessage[] = [];

        if (initialMessage) {
          newMessages.push({
            id: `user-${Date.now()}`,
            role: "user",
            content: initialMessage,
            timestamp: Date.now() / 1000,
          });
        }

        newMessages.push({
          id: `assistant-${Date.now()}`,
          role: "assistant",
          content: resp.message,
          timestamp: Date.now() / 1000,
          intent: resp.intent || undefined,
        });

        setMessages(newMessages);
      } catch (err: any) {
        setError(err?.message || "Failed to start conversation");
      } finally {
        setIsLoading(false);
      }
    },
    [linkedProfile]
  );

  // ------------------------------------------------------------------
  // Send message (non-streaming fallback)
  // ------------------------------------------------------------------

  const sendMessage = useCallback(
    async (text: string) => {
      if (!text.trim() || isLoading) return;

      const userMsg: ChatMessage = {
        id: `user-${Date.now()}`,
        role: "user",
        content: text.trim(),
        timestamp: Date.now() / 1000,
      };

      setMessages((prev) => [...prev, userMsg]);
      setInput("");
      setIsLoading(true);
      setError(null);

      // If no conversation yet, start one with this message
      if (!conversationId) {
        await startConversation(text.trim());
        setIsLoading(false);
        return;
      }

      try {
        // Add a placeholder for streaming
        const assistantId = `assistant-${Date.now()}`;
        setMessages((prev) => [
          ...prev,
          {
            id: assistantId,
            role: "assistant",
            content: "",
            timestamp: Date.now() / 1000,
            isStreaming: true,
          },
        ]);

        // Try streaming first
        let streamedContent = "";
        const abort = aiAdvisorApi.streamMessage(
          conversationId,
          text.trim(),
          // onToken
          (token: string) => {
            streamedContent += token;
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId
                  ? { ...m, content: streamedContent }
                  : m
              )
            );
          },
          // onDone
          () => {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId
                  ? { ...m, isStreaming: false }
                  : m
              )
            );
            setIsLoading(false);
          },
          // onError — fall back to non-streaming
          async () => {
            try {
              const resp = await aiAdvisorApi.sendMessage(conversationId!, {
                message: text.trim(),
              });
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId
                    ? {
                        ...m,
                        content: resp.message,
                        intent: resp.intent || undefined,
                        isStreaming: false,
                      }
                    : m
                )
              );
            } catch (fallbackErr: any) {
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId
                    ? {
                        ...m,
                        content:
                          "I'm having trouble responding right now. Please try again.",
                        isStreaming: false,
                      }
                    : m
                )
              );
            }
            setIsLoading(false);
          }
        );

        abortRef.current = abort;
      } catch (err: any) {
        setError(err?.message || "Failed to send message");
        setIsLoading(false);
      }
    },
    [conversationId, isLoading, startConversation]
  );

  // ------------------------------------------------------------------
  // Link profile
  // ------------------------------------------------------------------

  const handleLinkProfile = useCallback(
    (id?: string) => {
      const pid = id || profileId.trim();
      if (!pid) return;
      setProfileId(pid);
      setLinkedProfile(pid);
      setMessages([]);
      setConversationId(null);
    },
    [profileId]
  );

  // Auto-select the first profile once they load
  useEffect(() => {
    if (profiles.length > 0 && !linkedProfile && !profileId) {
      const first = profiles[0]!.profile_id;
      setProfileId(first);
      setLinkedProfile(first);
    }
  }, [profiles]);

  // ------------------------------------------------------------------
  // Key handler
  // ------------------------------------------------------------------

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input);
    }
  };

  // ------------------------------------------------------------------
  // Render
  // ------------------------------------------------------------------

  return (
    <div className="flex h-[calc(100vh-4rem)] flex-col">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-gray-200 bg-white px-6 py-3">
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-gradient-to-br from-brand-500 to-emerald-500 text-white">
            <Bot className="h-5 w-5" />
          </div>
          <div>
            <h2 className="text-lg font-semibold text-gray-900">
              Krishi Mitra
            </h2>
            <p className="text-xs text-gray-500">
              AI Credit Advisor{" "}
              {linkedProfile && (
                <span className="text-brand-600">
                  — {linkedProfileName || linkedProfile}
                </span>
              )}
            </p>
          </div>
        </div>

        {/* Profile selector */}
        <div className="flex items-center gap-2">
          {profilesLoading ? (
            <span className="text-xs text-gray-400">Loading…</span>
          ) : profiles.length > 0 ? (
            <div className="relative">
              <select
                value={profileId}
                onChange={(e) => handleLinkProfile(e.target.value)}
                className="w-56 appearance-none rounded-lg border border-gray-300 bg-white px-3 py-1.5 pr-8 text-sm text-gray-900 focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
              >
                <option value="" disabled>
                  Choose a borrower…
                </option>
                {profiles.map((p) => (
                  <option key={p.profile_id} value={p.profile_id}>
                    {p.name} — {p.location} ({p.occupation})
                  </option>
                ))}
              </select>
              <ChevronDown className="pointer-events-none absolute right-2 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
            </div>
          ) : (
            <>
              <input
                type="text"
                placeholder="Profile ID"
                value={profileId}
                onChange={(e) => setProfileId(e.target.value)}
                className="w-40 rounded-lg border border-gray-300 px-3 py-1.5 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
              />
              <Button
                size="sm"
                variant="outline"
                onClick={() => handleLinkProfile()}
                disabled={!profileId.trim()}
              >
                Link
              </Button>
            </>
          )}
          {conversationId && (
            <Button
              size="sm"
              variant="ghost"
              icon={<RefreshCw className="h-4 w-4" />}
              onClick={() => {
                setMessages([]);
                setConversationId(null);
                abortRef.current?.();
              }}
            >
              New Chat
            </Button>
          )}
        </div>
      </div>

      {/* Messages area */}
      <div
        ref={messagesContainerRef}
        className="relative flex-1 overflow-y-auto bg-gray-50 px-4 py-6"
      >
        {messages.length === 0 ? (
          <WelcomeScreen
            onQuickAction={(text) => sendMessage(text)}
            onStart={() => startConversation()}
            isLoading={isLoading}
          />
        ) : (
          <div className="mx-auto max-w-3xl space-y-4">
            {messages.map((msg) => (
              <MessageBubble key={msg.id} message={msg} />
            ))}
            <div ref={messagesEndRef} />
          </div>
        )}

        {/* Scroll-to-bottom button */}
        {showScrollButton && (
          <button
            onClick={scrollToBottom}
            className="absolute bottom-4 right-4 rounded-full bg-white p-2 shadow-lg ring-1 ring-gray-200 transition-all hover:shadow-xl"
          >
            <ArrowDown className="h-5 w-5 text-gray-600" />
          </button>
        )}
      </div>

      {/* Error banner */}
      {error && (
        <div className="bg-red-50 px-6 py-2 text-center text-sm text-red-600">
          {error}
        </div>
      )}

      {/* Input area */}
      <div className="border-t border-gray-200 bg-white px-4 py-3">
        <div className="mx-auto flex max-w-3xl items-end gap-3">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask Krishi Mitra anything about loans, risk, or finances..."
            rows={1}
            className="flex-1 resize-none rounded-xl border border-gray-300 px-4 py-3 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
            style={{
              minHeight: "44px",
              maxHeight: "120px",
              height: "auto",
            }}
            onInput={(e) => {
              const target = e.target as HTMLTextAreaElement;
              target.style.height = "auto";
              target.style.height = `${Math.min(target.scrollHeight, 120)}px`;
            }}
          />
          <button
            onClick={() => sendMessage(input)}
            disabled={!input.trim() || isLoading}
            className={cn(
              "flex h-11 w-11 items-center justify-center rounded-xl transition-all",
              input.trim() && !isLoading
                ? "bg-brand-600 text-white hover:bg-brand-700"
                : "bg-gray-100 text-gray-400"
            )}
          >
            {isLoading ? (
              <Loader2 className="h-5 w-5 animate-spin" />
            ) : (
              <Send className="h-5 w-5" />
            )}
          </button>
        </div>
        <p className="mt-1 text-center text-[10px] text-gray-400">
          Krishi Mitra provides guidance only — always consult a bank officer
          for final decisions
        </p>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function WelcomeScreen({
  onQuickAction,
  onStart,
  isLoading,
}: {
  onQuickAction: (text: string) => void;
  onStart: () => void;
  isLoading: boolean;
}) {
  return (
    <div className="mx-auto flex max-w-2xl flex-col items-center justify-center py-12">
      <div className="mb-6 flex h-20 w-20 items-center justify-center rounded-full bg-gradient-to-br from-brand-500 to-emerald-500 text-white shadow-lg">
        <Sparkles className="h-10 w-10" />
      </div>
      <h2 className="text-2xl font-bold text-gray-900">
        Namaste! I'm Krishi Mitra
      </h2>
      <p className="mt-2 text-center text-gray-500">
        Your AI credit advisor for rural finance. Ask me about loans,
        risk, cash flow, government schemes, or any financial question.
      </p>

      <div className="mt-8 grid w-full grid-cols-2 gap-3 sm:grid-cols-3">
        {QUICK_ACTIONS.map(({ label, icon }) => (
          <button
            key={label}
            onClick={() => onQuickAction(label)}
            disabled={isLoading}
            className="flex items-center gap-2 rounded-xl border border-gray-200 bg-white p-3 text-left text-sm text-gray-700 transition-all hover:border-brand-300 hover:bg-brand-50 hover:text-brand-700 disabled:opacity-50"
          >
            <span className="text-lg">{icon}</span>
            <span>{label}</span>
          </button>
        ))}
      </div>

      <Button
        variant="outline"
        size="lg"
        className="mt-6"
        onClick={onStart}
        loading={isLoading}
        icon={<MessageCircle className="h-5 w-5" />}
      >
        Start Conversation
      </Button>
    </div>
  );
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const isUser = message.role === "user";

  return (
    <div
      className={cn(
        "flex gap-3",
        isUser ? "flex-row-reverse" : "flex-row"
      )}
    >
      {/* Avatar */}
      <div
        className={cn(
          "flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full",
          isUser
            ? "bg-brand-100 text-brand-700"
            : "bg-gradient-to-br from-brand-500 to-emerald-500 text-white"
        )}
      >
        {isUser ? (
          <User className="h-4 w-4" />
        ) : (
          <Bot className="h-4 w-4" />
        )}
      </div>

      {/* Bubble */}
      <div
        className={cn(
          "max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-relaxed",
          isUser
            ? "bg-brand-600 text-white"
            : "bg-white text-gray-800 shadow-sm ring-1 ring-gray-100"
        )}
      >
        {message.content ? (
          isUser ? (
            message.content
          ) : (
            <ReactMarkdown
              components={{
                p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
                strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
                ul: ({ children }) => <ul className="mb-2 ml-4 list-disc space-y-1 last:mb-0">{children}</ul>,
                ol: ({ children }) => <ol className="mb-2 ml-4 list-decimal space-y-1 last:mb-0">{children}</ol>,
                li: ({ children }) => <li>{children}</li>,
              }}
            >
              {message.content}
            </ReactMarkdown>
          )
        ) : (
          <span className="flex items-center gap-2 text-gray-400">
            <Loader2 className="h-4 w-4 animate-spin" />
            Thinking...
          </span>
        )}
        {message.isStreaming && message.content && (
          <span className="ml-1 inline-block h-3 w-1 animate-pulse bg-brand-500" />
        )}
      </div>
    </div>
  );
}

// Re-export for barrel
export default AIAdvisorPage;
