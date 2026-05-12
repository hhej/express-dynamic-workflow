'use client';
import { useState, type FormEvent, type KeyboardEvent } from 'react';
import clsx from 'clsx';

interface Props {
  onSend: (message: string) => void;
  disabled?: boolean;
  /** Plan 06-02 D-08 — overrides the default placeholder when provided. */
  placeholder?: string;
}

export function ChatInput({
  onSend,
  disabled = false,
  placeholder = 'Ask about a surcharge, e.g., 15kg Bounce from Bang Na to Nonthaburi',
}: Props) {
  const [text, setText] = useState('');

  function submit(e?: FormEvent) {
    e?.preventDefault();
    const trimmed = text.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setText('');
  }

  function onKey(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  }

  return (
    <form
      onSubmit={submit}
      className="flex items-end gap-2 bg-transparent p-4"
    >
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={onKey}
        disabled={disabled}
        rows={2}
        placeholder={placeholder}
        className="flex-1 resize-none rounded border border-white/15 bg-white/5 backdrop-blur-md p-2 text-sm font-normal text-text-primary placeholder:text-text-muted focus:border-brand-via focus:outline-none focus:ring-2 focus:ring-brand-via/40 disabled:bg-white/5 disabled:opacity-60"
      />
      <button
        type="submit"
        aria-label="Send message"
        disabled={disabled || text.trim().length === 0}
        className={clsx(
          'rounded px-4 py-2 text-sm font-semibold text-white',
          'bg-blue-600 hover:bg-blue-700',
          'brand-gradient shadow-md shadow-brand-from/30 hover:brightness-110',
          'disabled:bg-gray-300 disabled:cursor-not-allowed disabled:bg-white/10 disabled:opacity-50',
        )}
      >
        Send
      </button>
    </form>
  );
}
