'use client';
import { EXAMPLE_PROMPTS } from '@/lib/constants';

interface Props {
  onClick: (prompt: string) => void;
}

export function ExamplePrompts({ onClick }: Props) {
  return (
    <div className="space-y-2">
      <p className="text-xs font-normal text-gray-500">Try one:</p>
      <ul className="flex flex-col gap-2">
        {EXAMPLE_PROMPTS.map((prompt) => (
          <li key={prompt}>
            <button
              type="button"
              onClick={() => onClick(prompt)}
              className="rounded border border-blue-200 bg-white px-3 py-1 text-sm font-normal text-blue-600 hover:bg-blue-50"
            >
              {prompt}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
