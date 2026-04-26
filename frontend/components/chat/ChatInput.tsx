'use client';
import { useState, type FormEvent, type KeyboardEvent } from 'react';
import clsx from 'clsx';

interface Props {
  onSend: (message: string) => void;
  disabled?: boolean;
}

export function ChatInput({ onSend, disabled = false }: Props) {
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
      className="flex items-end gap-2 border-t border-gray-200 bg-white p-4"
    >
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={onKey}
        disabled={disabled}
        rows={2}
        placeholder="Ask about a surcharge, e.g., 15kg Bounce from Bangkok to Nonthaburi"
        className="flex-1 resize-none rounded border border-gray-200 bg-white p-2 text-sm font-normal text-gray-700 focus:border-blue-600 focus:outline-none disabled:bg-gray-50"
      />
      <button
        type="submit"
        aria-label="Send message"
        disabled={disabled || text.trim().length === 0}
        className={clsx(
          'rounded px-4 py-2 text-sm font-semibold text-white',
          'bg-blue-600 hover:bg-blue-700',
          'disabled:bg-gray-300 disabled:cursor-not-allowed',
        )}
      >
        Send
      </button>
    </form>
  );
}
