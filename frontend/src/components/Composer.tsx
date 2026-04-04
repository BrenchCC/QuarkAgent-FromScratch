import { useState } from "react";
import type { FormEvent, KeyboardEvent } from "react";

interface ComposerProps {
  disabled: boolean;
  placeholder: string;
  onSubmit: (message: string) => Promise<void>;
}

export default function Composer(props: ComposerProps) {
  const { disabled, placeholder, onSubmit } = props;
  const [message, setMessage] = useState<string>("");

  const submitCurrentMessage = async (): Promise<void> => {
    const trimmedMessage = message.trim();
    if (!trimmedMessage || disabled) {
      return;
    }

    await onSubmit(trimmedMessage);
    setMessage("");
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>): Promise<void> => {
    event.preventDefault();
    await submitCurrentMessage();
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>): void => {
    if (disabled || event.nativeEvent.isComposing) {
      return;
    }

    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void submitCurrentMessage();
    }
  };

  return (
    <form className="composer" onSubmit={handleSubmit}>
      <textarea
        value={message}
        disabled={disabled}
        placeholder={placeholder}
        onChange={(event) => setMessage(event.target.value)}
        onKeyDown={handleKeyDown}
      />
      <button type="submit" disabled={disabled || message.trim().length === 0}>
        Send
      </button>
      <p className="composer-hint">
        Enter 发送，Shift + Enter 换行。输入 <code>/skills</code> 查看说明，输入 <code>/skills &lt;name&gt;</code> 查看详情。
      </p>
    </form>
  );
}
