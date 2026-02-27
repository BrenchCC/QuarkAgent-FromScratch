import ChatPanel from "./components/ChatPanel";
import Composer from "./components/Composer";
import EventTimeline from "./components/EventTimeline";
import { useChatSession } from "./hooks/useChatSession";

export default function App() {
  const {
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
  } = useChatSession();

  return (
    <div className="app-shell">
      <header className="hero">
        <div>
          <p className="eyebrow">QuarkAgent Web / MVP</p>
          <h1>Editorial Console</h1>
          <p>单会话 SSE 调试台，实时查看 status、tool_start、tool_end、final、error、done 事件。</p>
        </div>
        <div className="session-meta">
          <span>Session</span>
          <strong>{sessionId || "not ready"}</strong>
        </div>
      </header>

      {error ? <section className="error-banner">{error}</section> : null}

      <main className="workspace">
        <section className="chat-column">
          <ChatPanel messages={messages} isStreaming={isStreaming} statusText={statusText} />
          <Composer
            disabled={isInitializing || isStreaming}
            placeholder={isInitializing ? "Initializing session..." : "输入你的任务，例如：帮我分析项目结构并给出重构建议"}
            onSubmit={sendMessage}
          />
          <div className="actions">
            <button type="button" onClick={refreshSession} disabled={isStreaming}>
              Reconnect Session
            </button>
            <button type="button" onClick={clearConversation} disabled={isStreaming}>
              Clear Conversation
            </button>
            <button type="button" onClick={cancelStreaming} disabled={!isStreaming}>
              Cancel Stream
            </button>
          </div>
        </section>

        <EventTimeline events={timeline} />
      </main>
    </div>
  );
}
