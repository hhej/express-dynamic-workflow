'use client';
import { MarkdownAnswer } from '@/components/chat/MarkdownAnswer';
import { ClarifyCard } from '@/components/chat/ClarifyCard';
import { PartialCard } from '@/components/chat/PartialCard';
import { FeedbackButtons } from '@/components/chat/FeedbackButtons';
import type { FinalPayload } from '@/types/agent.types';

export interface UserMessage {
  role: 'user';
  content: string;
}

export interface AssistantMessage {
  role: 'assistant';
  id: string;
  payload: FinalPayload;
}

export type ChatMessage = UserMessage | AssistantMessage;

interface Props {
  messages: ChatMessage[];
  threadId: string | null;
}

function renderAssistant(payload: FinalPayload) {
  switch (payload.status) {
    case 'clarify':
      return <ClarifyCard payload={payload} />;
    case 'partial':
      return <PartialCard payload={payload} />;
    case 'ok':
    default:
      return <MarkdownAnswer payload={payload} />;
  }
}

export function MessageList({ messages, threadId }: Props) {
  return (
    <ol
      className="flex flex-1 flex-col gap-4 overflow-y-auto p-4"
      aria-live="polite"
    >
      {messages.map((m, i) => {
        if (m.role === 'user') {
          return (
            <li
              key={`u-${i}`}
              className="max-w-[75%] self-end rounded-lg bg-blue-600 px-4 py-2 text-sm text-white"
            >
              {m.content}
            </li>
          );
        }
        return (
          <li
            key={`a-${m.id}`}
            className="max-w-[85%] space-y-2 self-start rounded-lg bg-white px-4 py-2 text-sm text-gray-900"
          >
            {renderAssistant(m.payload)}
            {threadId && <FeedbackButtons threadId={threadId} messageId={m.id} />}
          </li>
        );
      })}
    </ol>
  );
}
