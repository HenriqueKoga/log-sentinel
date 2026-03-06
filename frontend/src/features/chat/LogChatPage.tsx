import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import ReactMarkdown from "react-markdown";
import { Trash2 } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import {
  useChatMessages,
  useChatSessions,
  useCreateChatSession,
  useDeleteChatSession,
  sendChatMessageStream,
  type ChatMessage as ChatMessageType,
} from "./api";

const QUICK_PROMPTS = [
  "chat.quickPrompt1",
  "chat.quickPrompt2",
  "chat.quickPrompt3",
] as const;

const PROCESSING_STEPS = [
  "Searching logs...",
  "Analyzing error patterns...",
  "Generating response...",
] as const;

function ProcessingIndicator() {
  const [stepIndex, setStepIndex] = useState(0);

  useEffect(() => {
    const id = setInterval(() => {
      setStepIndex((i) => (i + 1) % PROCESSING_STEPS.length);
    }, 1800);
    return () => clearInterval(id);
  }, []);

  return (
    <div className="flex justify-start">
      <div className="max-w-[85%] rounded-2xl rounded-bl-md border border-white/10 bg-slate-800/80 px-4 py-3 text-sm text-slate-400">
        <span className="inline-flex items-center gap-1.5">
          <span className="flex gap-1">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-slate-500 [animation-delay:0ms]" />
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-slate-500 [animation-delay:150ms]" />
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-slate-500 [animation-delay:300ms]" />
          </span>
          {PROCESSING_STEPS[stepIndex]}
        </span>
      </div>
    </div>
  );
}

export function LogChatPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [selectedSessionId, setSelectedSessionId] = useState<number | null>(null);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [streamingContent, setStreamingContent] = useState<string | null>(null);
  const [pendingUserMessage, setPendingUserMessage] = useState<string | null>(null);

  const sessionsQuery = useChatSessions(null);
  const messagesQuery = useChatMessages(selectedSessionId);
  const createSession = useCreateChatSession();
  const deleteSession = useDeleteChatSession();

  const sessions = sessionsQuery.data?.items ?? [];

  const handleDeleteSession = useCallback(
    (e: React.MouseEvent, sessionId: number) => {
      e.stopPropagation();
      deleteSession.mutate(sessionId, {
        onSuccess: () => {
          if (selectedSessionId === sessionId) {
            setSelectedSessionId(null);
          }
        },
      });
    },
    [deleteSession, selectedSessionId],
  );
  const messages = messagesQuery.data?.items ?? [];

  const messagesContainerRef = useRef<HTMLDivElement | null>(null);

  const handleNewChat = useCallback(() => {
    createSession.mutate(
      { project_id: null, title: "" },
      {
        onSuccess: (session) => {
          setSelectedSessionId(session.id);
          queryClient.invalidateQueries({ queryKey: ["chat-messages", session.id] });
        },
      },
    );
  }, [createSession, queryClient]);

  const sendMessage = useCallback(async () => {
    const content = input.trim();
    if (!content || selectedSessionId == null || sending) return;
    setInput("");
    setPendingUserMessage(content);
    setSending(true);
    setStreamingContent("");
    try {
      await sendChatMessageStream(
        selectedSessionId,
        content,
        (chunk) => setStreamingContent((prev) => (prev ?? "") + chunk),
        () => {
          setPendingUserMessage(null);
          setStreamingContent(null);
          queryClient.invalidateQueries({ queryKey: ["chat-messages", selectedSessionId] });
          queryClient.invalidateQueries({ queryKey: ["chat-sessions"] });
        },
      );
    } catch {
      setPendingUserMessage(null);
      setStreamingContent(null);
      queryClient.invalidateQueries({ queryKey: ["chat-messages", selectedSessionId] });
    } finally {
      setSending(false);
    }
  }, [input, selectedSessionId, sending, queryClient]);

  const handleQuickPrompt = useCallback(
    (key: (typeof QUICK_PROMPTS)[number]) => {
      const text = t(key);
      setInput(text);
    },
    [t],
  );

  // Always keep scroll at the bottom when messages or streaming content change
  useEffect(() => {
    const el = messagesContainerRef.current;
    if (!el) return;
    el.scrollTop = el.scrollHeight;
  }, [messages.length, streamingContent, pendingUserMessage]);

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden">
      <div className="flex flex-shrink-0 flex-wrap items-center gap-3">
        <h1 className="text-2xl font-semibold tracking-tight text-slate-100">
          {t("chat.title")}
        </h1>
      </div>
      <div className="mt-4 flex min-h-0 max-h-[calc(100vh-12rem)] flex-1 gap-4 overflow-hidden">
        {/* Left: sessions list */}
        <div className="flex w-56 flex-shrink-0 flex-col rounded-2xl border border-white/5 bg-black/30">
          <button
            type="button"
            onClick={handleNewChat}
            className="m-3 cursor-pointer rounded-lg border border-primary/40 bg-primary/20 px-3 py-2 text-sm font-medium text-slate-100 hover:bg-primary/30"
          >
            {t("chat.newChat")}
          </button>
          <div className="flex-1 overflow-y-auto px-2 pb-2">
            {sessionsQuery.isLoading && (
              <p className="px-2 py-4 text-xs text-slate-500">{t("common.loading")}</p>
            )}
            {sessions.map((s) => (
              <div
                key={s.id}
                role="button"
                tabIndex={0}
                onClick={() => setSelectedSessionId(s.id)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    setSelectedSessionId(s.id);
                  }
                }}
                className={`mb-1 flex w-full cursor-pointer items-center justify-between gap-2 rounded-lg px-3 py-2 text-left text-sm ${
                  selectedSessionId === s.id
                    ? "bg-white/10 text-slate-100"
                    : "text-slate-400 hover:bg-white/5 hover:text-slate-200"
                }`}
              >
                <span className="min-w-0 flex-1 truncate">
                  {s.title || t("chat.untitled")}
                </span>
                <button
                  type="button"
                  onClick={(e) => handleDeleteSession(e, s.id)}
                  className="flex-shrink-0 cursor-pointer rounded p-1 text-slate-500 hover:bg-white/10 hover:text-red-400"
                  aria-label={t("chat.deleteSession")}
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            ))}
          </div>
        </div>
        {/* Right: messages + composer */}
        <div className="flex min-h-0 min-w-0 flex-1 flex-col rounded-2xl border border-white/5 bg-black/30">
          {selectedSessionId == null ? (
            <div className="flex flex-1 items-center justify-center p-8 text-slate-500">
              {t("chat.emptyState")}
            </div>
          ) : (
            <>
              <div ref={messagesContainerRef} className="min-h-0 flex-1 overflow-y-auto p-4">
                {messagesQuery.isLoading && (
                  <p className="text-sm text-slate-500">{t("common.loading")}</p>
                )}
                <div className="space-y-4">
                  {messages.map((m) => (
                    <MessageBubble key={m.id} message={m} />
                  ))}
                  {pendingUserMessage != null && (
                    <div className="flex justify-end">
                      <div className="max-w-[85%] rounded-2xl rounded-br-md border border-primary/30 bg-primary/20 px-4 py-3 text-sm text-slate-100">
                        <p className="whitespace-pre-wrap">{pendingUserMessage}</p>
                      </div>
                    </div>
                  )}
                  {sending && (streamingContent == null || streamingContent === "") && (
                    <ProcessingIndicator />
                  )}
                  {streamingContent != null && streamingContent !== "" && (
                    <div className="flex justify-start">
                      <div className="max-w-[85%] rounded-2xl rounded-bl-md border border-white/10 bg-slate-800/80 px-4 py-3 text-sm text-slate-200">
                        <ReactMarkdown>{streamingContent}</ReactMarkdown>
                      </div>
                    </div>
                  )}
                </div>
              </div>
              <div className="border-t border-white/5 p-3">
                <div className="mb-2 flex flex-wrap gap-2">
                  {QUICK_PROMPTS.map((key) => (
                    <button
                      key={key}
                      type="button"
                      onClick={() => handleQuickPrompt(key)}
                      className="cursor-pointer rounded-full border border-white/20 bg-white/5 px-3 py-1 text-xs text-slate-400 hover:border-white/30 hover:text-slate-200"
                    >
                      {t(key)}
                    </button>
                  ))}
                </div>
                <div className="flex gap-2">
                  <textarea
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && !e.shiftKey) {
                        e.preventDefault();
                        sendMessage();
                      }
                    }}
                    placeholder={t("chat.placeholder")}
                    rows={2}
                    className="min-h-[52px] flex-1 resize-none rounded-xl border border-white/10 bg-black/40 px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 focus:border-primary/50 focus:outline-none"
                  />
                  <button
                    type="button"
                    onClick={sendMessage}
                    disabled={sending || !input.trim()}
                    className="flex h-[52px] cursor-pointer items-center justify-center rounded-xl bg-primary/30 px-4 text-sm font-medium text-slate-100 hover:bg-primary/40 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {sending ? t("chat.loading") : t("chat.send")}
                  </button>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function MessageBubble({ message }: { message: ChatMessageType }) {
  const isUser = message.role === "user";
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm ${
          isUser
            ? "rounded-br-md border border-primary/30 bg-primary/20 text-slate-100"
            : "rounded-bl-md border border-white/10 bg-slate-800/80 text-slate-200"
        }`}
      >
        {isUser ? (
          <p className="whitespace-pre-wrap">{message.content}</p>
        ) : (
          <div className="prose prose-invert prose-sm max-w-none">
            <ReactMarkdown>{message.content}</ReactMarkdown>
          </div>
        )}
      </div>
    </div>
  );
}
