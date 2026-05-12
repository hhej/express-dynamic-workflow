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
  /** Plan 06-02 D-13 — optional error message forwarded to ApprovalCard. */
  approvalErrorMessage?: string | null;
}

function renderAssistant(
  msg: AssistantMessage,
  awaitingApproval: ApprovalPayload | null | undefined,
  onApprove: (() => void | Promise<void>) | undefined,
  onDeny: (() => void | Promise<void>) | undefined,
  approvalErrorMessage: string | null | undefined,
) {
  // Plan 05-06 D-06: when awaiting approval, replace MarkdownAnswer with ApprovalCard.
  if (awaitingApproval && onApprove && onDeny) {
    return (
      <ApprovalCard
        payload={awaitingApproval}
        onApprove={onApprove}
        onDeny={onDeny}
        errorMessage={approvalErrorMessage}
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
    case 'search_only':
      // Phase 8 D-11: explicit dispatch to MarkdownAnswer, which renders
      // SearchContextLine above the prose when payload.search_context.summary
      // is present. Explicit case > default fallthrough so a future status
      // (e.g. 'partial_news') gets a named extension point.
      return <MarkdownAnswer payload={payload} />;
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
  approvalErrorMessage,
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
              className="max-w-[75%] self-end rounded-lg bg-blue-600 brand-gradient px-4 py-2 text-sm text-white shadow-md shadow-brand-from/30"
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
            // Debug 999.5 (2026-05-09): key reverted from `a-${m.id}-${i}`
            // back to `a-${m.id}`. The `-${i}` suffix was a defensive band-aid
            // shipped in quick task 260509-e0p that masked the real duplicate-
            // append bug in ChatApp.tsx. With the real fix in place
            // (handleResume guard-seed + done-effect dep narrowing), m.id —
            // which is the BE-stamped message_id `{thread_id}-{turn_idx}` for
            // canonical assistants and `replay-noncanonical-${i}` for HITL
            // pre-pause partials — is unique within `messages`. Using array
            // index in keys is a React anti-pattern: it silently masks
            // reconciliation bugs and breaks list-update animations / focus
            // retention. If a future regression ever lets a duplicate id slip
            // through, we WANT React to warn so we can chase the root cause.
            key={`a-${m.id}`}
            className="max-w-[85%] space-y-2 self-start glass-surface px-4 py-2 text-sm text-text-primary"
          >
            {renderAssistant(m, slotApproval, onApprove, onDeny, approvalErrorMessage)}
            {threadId && m.payload && m.payload.message_id && !slotApproval && (
              <FeedbackButtons threadId={threadId} messageId={m.payload.message_id} />
            )}
          </li>
        );
      })}
    </ol>
  );
}
