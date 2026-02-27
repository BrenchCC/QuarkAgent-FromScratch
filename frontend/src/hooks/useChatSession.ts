import { useCallback, useEffect, useRef, useState } from "react";

import { createSession, streamChat } from "../lib/api";
import type { ChatMessage, StreamEvent, TimelineEvent } from "../types/api";

interface UseChatSessionReturn {
  sessionId: string;
  messages: ChatMessage[];
  timeline: TimelineEvent[];
  isInitializing: boolean;
  isStreaming: boolean;
  statusText: string;
  error: string;
  sendMessage: (message: string) => Promise<void>;
  refreshSession: () => Promise<string>;
  clearConversation: () => void;
  cancelStreaming: () => void;
}

function createMessageId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }

  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function createTimelineEvent(event: StreamEvent): TimelineEvent {
  return {
    id: createMessageId(),
    type: event.type,
    timestamp: event.timestamp,
    data: event.data,
  };
}

function readDataString(source: Record<string, unknown>, field: string): string {
  const value = source[field];
  return typeof value === "string" ? value : "";
}

export function useChatSession(): UseChatSessionReturn {
  const [sessionId, setSessionId] = useState<string>("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [timeline, setTimeline] = useState<TimelineEvent[]>([]);
  const [isInitializing, setIsInitializing] = useState<boolean>(false);
  const [isStreaming, setIsStreaming] = useState<boolean>(false);
  const [statusText, setStatusText] = useState<string>("等待输入");
  const [error, setError] = useState<string>("");
  const abortControllerRef = useRef<AbortController | null>(null);

  const appendTimelineEvent = useCallback((event: StreamEvent): void => {
    setTimeline((previous) => [createTimelineEvent(event), ...previous].slice(0, 100));
  }, []);

  const appendMessage = useCallback((role: "user" | "assistant", content: string): void => {
    const nextMessage: ChatMessage = {
      id: createMessageId(),
      role,
      content,
      timestamp: new Date().toISOString(),
    };

    setMessages((previous) => [...previous, nextMessage]);
  }, []);

  const refreshSession = useCallback(async (): Promise<string> => {
    setIsInitializing(true);
    setError("");

    try {
      const response = await createSession();
      setSessionId(response.session_id);
      setStatusText("会话已连接");
      return response.session_id;
    } catch (sessionError) {
      const nextError = sessionError instanceof Error ? sessionError.message : "Failed to create session.";
      setError(nextError);
      setStatusText("会话初始化失败");
      return "";
    } finally {
      setIsInitializing(false);
    }
  }, []);

  const clearConversation = useCallback((): void => {
    setMessages([]);
    setTimeline([]);
    setStatusText("等待输入");
    setError("");
  }, []);

  const cancelStreaming = useCallback((): void => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
      setIsStreaming(false);
      setStatusText("已取消");
    }
  }, []);

  const sendMessage = useCallback(async (message: string): Promise<void> => {
    const trimmedMessage = message.trim();
    if (!trimmedMessage || isStreaming) {
      return;
    }

    let effectiveSessionId = sessionId;
    if (!effectiveSessionId) {
      effectiveSessionId = await refreshSession();
    }

    if (!effectiveSessionId) {
      setError("Session is unavailable.");
      return;
    }

    setIsStreaming(true);
    setError("");
    setStatusText("准备发送");

    appendMessage("user", trimmedMessage);

    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      await streamChat({
        request: {
          session_id: effectiveSessionId,
          message: trimmedMessage,
        },
        signal: controller.signal,
        onEvent: (event: StreamEvent): void => {
          appendTimelineEvent(event);

          if (event.type === "status") {
            const nextStatus = readDataString(event.data, "message") || "处理中";
            setStatusText(nextStatus);
            return;
          }

          if (event.type === "tool_start") {
            const toolName = readDataString(event.data, "tool") || "tool";
            setStatusText(`执行工具: ${toolName}`);
            return;
          }

          if (event.type === "tool_end") {
            const toolName = readDataString(event.data, "tool") || "tool";
            setStatusText(`工具完成: ${toolName}`);
            return;
          }

          if (event.type === "final") {
            const answer = readDataString(event.data, "answer") || "(empty response)";
            appendMessage("assistant", answer);
            setStatusText("回答完成");
            return;
          }

          if (event.type === "error") {
            const nextError = readDataString(event.data, "message") || "Server error";
            setError(nextError);
            setStatusText("出现错误");
            return;
          }

          if (event.type === "done") {
            setStatusText("等待输入");
          }
        },
      });
    } catch (streamError) {
      const isAbortError = streamError instanceof DOMException && streamError.name === "AbortError";
      if (!isAbortError) {
        const nextError = streamError instanceof Error ? streamError.message : "Streaming request failed.";
        setError(nextError);
        setStatusText("连接失败");
      }
    } finally {
      abortControllerRef.current = null;
      setIsStreaming(false);
    }
  }, [appendMessage, appendTimelineEvent, isStreaming, refreshSession, sessionId]);

  useEffect(() => {
    void refreshSession();

    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, [refreshSession]);

  return {
    sessionId,
    messages,
    timeline,
    isInitializing,
    isStreaming,
    statusText,
    error,
    sendMessage,
    refreshSession,
    clearConversation,
    cancelStreaming,
  };
}
