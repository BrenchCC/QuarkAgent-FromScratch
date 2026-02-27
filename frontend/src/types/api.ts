export type StreamEventType = "status" | "tool_start" | "tool_end" | "final" | "error" | "done";

export interface SessionCreateResponse {
  session_id: string;
  created_at: string;
  expires_at: string;
}

export interface SessionDeleteResponse {
  session_id: string;
  deleted: boolean;
}

export interface ToolListResponse {
  tools: string[];
}

export interface ChatRequest {
  session_id: string;
  message: string;
  max_iterations?: number;
}

export interface StreamEvent {
  type: StreamEventType;
  timestamp: string;
  data: Record<string, unknown>;
}

export interface ChatResponse {
  session_id: string;
  answer: string;
  events: StreamEvent[];
  timestamp: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: string;
}

export interface TimelineEvent extends StreamEvent {
  id: string;
}

export interface StreamChatOptions {
  request: ChatRequest;
  onEvent: (event: StreamEvent) => void;
  signal?: AbortSignal;
  baseUrl?: string;
}
