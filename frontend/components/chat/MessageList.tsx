'use client';
import { MarkdownAnswer } from '@/components/chat/MarkdownAnswer';
import { ClarifyCard } from '@/components/chat/ClarifyCard';
import { PartialCard } from '@/components/chat/PartialCard';
import { ApprovalCard } from '@/components/chat/ApprovalCard';
import { FeedbackButtons } from '@/components/chat/FeedbackButtons';
import type { ApprovalPayload, FinalPayload } from '@/types/agent.types';

export interface UserMessage {
  role: 'user';
  content: string;
}

export interface AssistantMessage {
  role: 'assistant';
  id: string;
  /** Null while awaiting_approval — ApprovalCard renders in place of the answer. */
  payload: FinalPayload | null;
}

export type ChatMessage = UserMessage | AssistantMessage;

interface Props {
  messages: ChatMessage[];
  threadId: string | null;
  /** Plan 05-06 — sixth SSE event payload; renders ApprovalCard in the last assistant slot. */
  awaitingApproval?: ApprovalPayload | null;
  onApprove?: () => void | Promise<void>;
  onDeny?: () => void | Promise<void>;
}

function renderAssistant(
  msg: AssistantMessage,
  awaitingApproval: ApprovalPayload | null | undefined,
  onApprove: (() => void | Promise<void>) | undefined,
  onDeny: (() => void | Promise<void>) | undefined,
) {
  // Plan 05-06 D-06: when awaiting approval, replace MarkdownAnswer with ApprovalCard.
  if (awaitingApproval && onApprove && onDeny) {
    return (
      <ApprovalCard
        payload={awaitingApproval}
        onApprove={onApprove}
        onDeny={onDeny}
      />
    );
  }
  const payload = msg.payload;
  if (!payload) return null;
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

export function MessageList({
  messages,
  threadId,
  awaitingApproval,
  onApprove,
  onDeny,
}: Props) {
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
        // Only the LAST assistant message can host an approval card.
        const isLast = i === messages.length - 1;
        const slotApproval = isLast ? awaitingApproval : null;
        return (
          <li
            key={`a-${m.id}`}
            className="max-w-[85%] space-y-2 self-start rounded-lg bg-white px-4 py-2 text-sm text-gray-900"
          >
            {renderAssistant(m, slotApproval, onApprove, onDeny)}
            {threadId && m.payload && !slotApproval && (
              <FeedbackButtons threadId={threadId} messageId={m.id} />
            )}
          </li>
        );
      })}
    </ol>
  );
}
