'use client';
import { EXAMPLE_PROMPTS } from '@/lib/constants';

interface Props {
  onClick: (prompt: string) => void;
}

export function ExamplePrompts({ onClick }: Props) {
  return (
    <div className="space-y-2">
      <p className="text-xs font-normal text-text-muted">Try one:</p>
      <ul className="flex flex-col gap-2">
        {EXAMPLE_PROMPTS.map((prompt) => (
          <li key={prompt}>
            <button
              type="button"
              onClick={() => onClick(prompt)}
              className="rounded glass-surface border-brand-via/30 px-3 py-1 text-sm font-normal text-accent-violet hover:text-accent-cyan hover:border-accent-cyan/40"
            >
              {prompt}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
