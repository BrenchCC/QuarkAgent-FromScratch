import { useState } from "react";
import type { FormEvent } from "react";

interface ComposerProps {
  disabled: boolean;
  placeholder: string;
  onSubmit: (message: string) => Promise<void>;
}

export default function Composer(props: ComposerProps) {
  const { disabled, placeholder, onSubmit } = props;
  const [message, setMessage] = useState<string>("");

  const handleSubmit = async (event: FormEvent<HTMLFormElement>): Promise<void> => {
    event.preventDefault();

    const trimmedMessage = message.trim();
    if (!trimmedMessage || disabled) {
      return;
    }

    await onSubmit(trimmedMessage);
    setMessage("");
  };

  return (
    <form className="composer" onSubmit={handleSubmit}>
      <textarea
        value={message}
        disabled={disabled}
        placeholder={placeholder}
        onChange={(event) => setMessage(event.target.value)}
      />
      <button type="submit" disabled={disabled || message.trim().length === 0}>
        Send
      </button>
    </form>
  );
}
