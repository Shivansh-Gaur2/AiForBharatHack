/**
 * Floating AI Chat Widget — accessible from every page.
 *
 * A small FAB button in the bottom-right that expands into a chat panel.
 * Uses the same AI Advisor API as the full page.
 */

import { useState, useRef, useEffect, useCallback } from "react";
import {
  MessageCircle,
  X,
  Send,
  Bot,
  User,
  Loader2,
  Minimize2,
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import { cn } from "@/lib/utils";
import { aiAdvisorApi } from "@/api";

interface WidgetMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  isStreaming?: boolean;
}

export function ChatWidget() {
  const [isOpen, setIsOpen] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<WidgetMessage[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Focus input when opened
  useEffect(() => {
    if (isOpen) {
      setTimeout(() => inputRef.current?.focus(), 100);
    }
  }, [isOpen]);

  // ------------------------------------------------------------------
  // Send message
  // ------------------------------------------------------------------

  const handleSend = useCallback(async () => {
    const text = input.trim();
    if (!text || isLoading) return;

    const userMsg: WidgetMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      content: text,
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setIsLoading(true);

    const assistantId = `assistant-${Date.now()}`;
    setMessages((prev) => [
      ...prev,
      { id: assistantId, role: "assistant", content: "", isStreaming: true },
    ]);

    try {
      if (!conversationId) {
        // Start new conversation
        const resp = await aiAdvisorApi.startConversation({
          language: "en",
          message: text,
        });
        setConversationId(resp.conversation_id);
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId
              ? { ...m, content: resp.message, isStreaming: false }
              : m
          )
        );
      } else {
        // Continue conversation with streaming
        let streamedContent = "";
        aiAdvisorApi.streamMessage(
          conversationId,
          text,
          (token) => {
            streamedContent += token;
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId ? { ...m, content: streamedContent } : m
              )
            );
          },
          () => {
            setMessages((prev) =>
              prev.map((m) =>
                m.id === assistantId ? { ...m, isStreaming: false } : m
              )
            );
            setIsLoading(false);
          },
          async () => {
            // Fallback to non-streaming
            try {
              const resp = await aiAdvisorApi.sendMessage(conversationId!, {
                message: text,
              });
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId
                    ? { ...m, content: resp.message, isStreaming: false }
                    : m
                )
              );
            } catch {
              setMessages((prev) =>
                prev.map((m) =>
                  m.id === assistantId
                    ? {
                        ...m,
                        content: "Sorry, I couldn't respond. Please try again.",
                        isStreaming: false,
                      }
                    : m
                )
              );
            }
            setIsLoading(false);
          }
        );
        return; // Don't set isLoading false — streaming callbacks handle it
      }
    } catch {
      setMessages((prev) =>
        prev.map((m) =>
          m.id === assistantId
            ? {
                ...m,
                content: "Something went wrong. Please try again.",
                isStreaming: false,
              }
            : m
        )
      );
    }

    setIsLoading(false);
  }, [input, isLoading, conversationId]);

  return (
    <>
      {/* FAB Button */}
      {!isOpen && (
        <button
          onClick={() => setIsOpen(true)}
          className="fixed bottom-6 right-6 z-50 flex h-14 w-14 items-center justify-center rounded-full bg-gradient-to-br from-brand-500 to-emerald-500 text-white shadow-xl transition-all hover:scale-105 hover:shadow-2xl"
          title="Chat with Krishi Mitra"
        >
          <MessageCircle className="h-6 w-6" />
        </button>
      )}

      {/* Chat Panel */}
      {isOpen && (
        <div className="fixed bottom-6 right-6 z-50 flex h-[500px] w-[380px] flex-col overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-2xl">
          {/* Header */}
          <div className="flex items-center justify-between bg-gradient-to-r from-brand-600 to-emerald-600 px-4 py-3">
            <div className="flex items-center gap-2">
              <Bot className="h-5 w-5 text-white" />
              <div>
                <p className="text-sm font-semibold text-white">
                  Krishi Mitra
                </p>
                <p className="text-[10px] text-brand-100">AI Credit Advisor</p>
              </div>
            </div>
            <div className="flex items-center gap-1">
              <button
                onClick={() => setIsOpen(false)}
                className="rounded-lg p-1.5 text-white/70 transition-colors hover:bg-white/20 hover:text-white"
              >
                <Minimize2 className="h-4 w-4" />
              </button>
              <button
                onClick={() => setIsOpen(false)}
                className="rounded-lg p-1.5 text-white/70 transition-colors hover:bg-white/20 hover:text-white"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          </div>

          {/* Messages */}
          <div className="flex-1 overflow-y-auto bg-gray-50 px-3 py-3">
            {messages.length === 0 ? (
              <div className="flex h-full flex-col items-center justify-center text-center">
                <Bot className="mb-2 h-8 w-8 text-brand-400" />
                <p className="text-sm font-medium text-gray-700">
                  Namaste! I'm Krishi Mitra
                </p>
                <p className="mt-1 text-xs text-gray-500">
                  Ask me about loans, risk, or finances
                </p>
                <div className="mt-3 flex flex-wrap justify-center gap-1.5">
                  {["Loan advice", "My risk?", "Best time to borrow?"].map(
                    (q) => (
                      <button
                        key={q}
                        onClick={() => {
                          setInput(q);
                          setTimeout(() => handleSend(), 0);
                        }}
                        className="rounded-full border border-gray-200 bg-white px-3 py-1 text-xs text-gray-600 transition-colors hover:border-brand-300 hover:text-brand-600"
                      >
                        {q}
                      </button>
                    )
                  )}
                </div>
              </div>
            ) : (
              <div className="space-y-3">
                {messages.map((msg) => (
                  <div
                    key={msg.id}
                    className={cn(
                      "flex gap-2",
                      msg.role === "user" ? "flex-row-reverse" : "flex-row"
                    )}
                  >
                    <div
                      className={cn(
                        "flex h-6 w-6 flex-shrink-0 items-center justify-center rounded-full",
                        msg.role === "user"
                          ? "bg-brand-100 text-brand-700"
                          : "bg-gradient-to-br from-brand-500 to-emerald-500 text-white"
                      )}
                    >
                      {msg.role === "user" ? (
                        <User className="h-3 w-3" />
                      ) : (
                        <Bot className="h-3 w-3" />
                      )}
                    </div>
                    <div
                      className={cn(
                        "max-w-[75%] rounded-2xl px-3 py-2 text-xs leading-relaxed",
                        msg.role === "user"
                          ? "bg-brand-600 text-white"
                          : "bg-white text-gray-700 shadow-sm ring-1 ring-gray-100"
                      )}
                    >
                      {msg.content ? (
                        msg.role === "user" ? (
                          msg.content
                        ) : (
                          <ReactMarkdown
                            components={{
                              p: ({ children }) => <p className="mb-1.5 last:mb-0">{children}</p>,
                              strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
                              ul: ({ children }) => <ul className="mb-1.5 ml-3 list-disc space-y-0.5 last:mb-0">{children}</ul>,
                              ol: ({ children }) => <ol className="mb-1.5 ml-3 list-decimal space-y-0.5 last:mb-0">{children}</ol>,
                              li: ({ children }) => <li>{children}</li>,
                            }}
                          >
                            {msg.content}
                          </ReactMarkdown>
                        )
                      ) : (
                        <Loader2 className="h-3 w-3 animate-spin text-gray-400" />
                      )}
                      {msg.isStreaming && msg.content && (
                        <span className="ml-0.5 inline-block h-3 w-0.5 animate-pulse bg-brand-500" />
                      )}
                    </div>
                  </div>
                ))}
                <div ref={messagesEndRef} />
              </div>
            )}
          </div>

          {/* Input */}
          <div className="border-t border-gray-200 bg-white p-2">
            <div className="flex items-center gap-2">
              <input
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    handleSend();
                  }
                }}
                placeholder="Ask anything..."
                className="flex-1 rounded-lg border border-gray-200 px-3 py-2 text-xs focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
              />
              <button
                onClick={handleSend}
                disabled={!input.trim() || isLoading}
                className={cn(
                  "flex h-8 w-8 items-center justify-center rounded-lg transition-all",
                  input.trim() && !isLoading
                    ? "bg-brand-600 text-white hover:bg-brand-700"
                    : "bg-gray-100 text-gray-400"
                )}
              >
                {isLoading ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <Send className="h-3.5 w-3.5" />
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

export default ChatWidget;
