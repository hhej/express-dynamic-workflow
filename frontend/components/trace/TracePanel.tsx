'use client';
import { TraceStep } from '@/components/trace/TraceStep';
import { ExamplePrompts } from '@/components/chat/ExamplePrompts';
import type { TraceEntry } from '@/types/agent.types';

interface Props {
  entries: TraceEntry[];
  isStreaming: boolean;
  onExamplePromptClick: (text: string) => void;
}

export function TracePanel({
  entries,
  isStreaming,
  onExamplePromptClick,
}: Props) {
  const isEmpty = !isStreaming && entries.length === 0;

  return (
    <aside className="flex w-96 flex-col gap-3 border-l border-gray-200 bg-gray-50 p-4">
      <h2 className="text-base font-semibold">Reasoning trace</h2>
      {isEmpty ? (
        <div className="space-y-3">
          <p className="text-sm font-normal text-gray-700">
            When you ask a question, the agent&apos;s planner, fuel, route, and
            pricing steps will stream here in real time.
          </p>
          <ExamplePrompts onClick={onExamplePromptClick} />
        </div>
      ) : (
        <ol
          className="flex flex-col gap-2 overflow-y-auto"
          aria-live="polite"
        >
          {entries.map((entry) => (
            <TraceStep key={`${entry.step}-${entry.agent}`} entry={entry} />
          ))}
          {isStreaming && (
            <li className="animate-pulse text-xs italic text-gray-500">
              …thinking
            </li>
          )}
        </ol>
      )}
    </aside>
  );
}
