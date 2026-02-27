import type { ChatMessage } from "../types/api";

interface ChatPanelProps {
  messages: ChatMessage[];
  isStreaming: boolean;
  statusText: string;
}

function formatLocalTime(timestamp: string): string {
  const parsedDate = new Date(timestamp);
  if (Number.isNaN(parsedDate.getTime())) {
    return "--:--";
  }

  return parsedDate.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function ChatPanel(props: ChatPanelProps) {
  const { messages, isStreaming, statusText } = props;

  if (messages.length === 0) {
    return (
      <section className="chat-panel empty">
        <h2>QuarkAgent Web Console</h2>
        <p>输入一个任务，后端会通过 SSE 回传状态、工具执行过程和最终回答。</p>
        <p className="subline">当前状态: {statusText}</p>
      </section>
    );
  }

  return (
    <section className="chat-panel">
      {messages.map((message) => (
        <article key={message.id} className={`chat-message ${message.role}`}>
          <header>
            <span>{message.role === "user" ? "You" : "QuarkAgent"}</span>
            <time>{formatLocalTime(message.timestamp)}</time>
          </header>
          <p>{message.content}</p>
        </article>
      ))}
      <div className="chat-footer-state">
        <span className={`stream-dot ${isStreaming ? "active" : ""}`} />
        <span>{statusText}</span>
      </div>
    </section>
  );
}
