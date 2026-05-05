'use client';
import { useState } from 'react';
import clsx from 'clsx';
import { ChatInput } from '@/components/chat/ChatInput';
import { MessageList, type ChatMessage } from '@/components/chat/MessageList';
import { DashboardView } from '@/components/dashboard/DashboardView';
import type { ApprovalPayload } from '@/types/agent.types';

export type CenterTab = 'chat' | 'dashboard';

interface Props {
  messages: ChatMessage[];
  threadId: string | null;
  /** Plan 06-02 D-07 — RENAMED from isStreaming. True when chat is streaming OR awaiting approval. */
  inputDisabled: boolean;
  onSend: (message: string) => void;
  /** Plan 06-02 D-04 — sixth SSE event payload; rendered in the last assistant slot via MessageList. */
  awaitingApproval?: ApprovalPayload | null;
  onApprove?: () => void | Promise<void>;
  onDeny?: () => void | Promise<void>;
  /** Plan 06-02 D-13 — forwarded to ApprovalCard.errorMessage when set. */
  approvalErrorMessage?: string | null;
  /** Plan 06-02 D-08 — overrides ChatInput's default placeholder when set. */
  placeholder?: string;
}

/**
 * Center column of the three-column app shell. Owns the D-04 Chat | Dashboard
 * tab toggle. Both tab bodies stay mounted (Tailwind `hidden` toggles
 * visibility) so chat scroll/streaming state survives a tab switch.
 *
 * Locked invariants (UI-SPEC §Copywriting + §Color):
 *   - Tab labels: "Chat" | "Dashboard"
 *   - Active tab: bg-blue-600 + text-white (accent)
 *   - Inactive tab: bg-white + text-gray-700
 */
export function ChatColumn({
  messages,
  threadId,
  inputDisabled,
  onSend,
  awaitingApproval,
  onApprove,
  onDeny,
  approvalErrorMessage,
  placeholder,
}: Props) {
  const [tab, setTab] = useState<CenterTab>('chat');

  return (
    <div className="flex flex-1 flex-col bg-white">
      <div className="flex items-center gap-1 border-b border-gray-200 p-2">
        <TabButton
          active={tab === 'chat'}
          onClick={() => setTab('chat')}
          label="Chat"
        />
        <TabButton
          active={tab === 'dashboard'}
          onClick={() => setTab('dashboard')}
          label="Dashboard"
        />
      </div>
      {/*
       * Render BOTH tab bodies and toggle visibility — this preserves chat state
       * (scroll position, in-flight stream, etc.) when the user pops to the
       * dashboard and back. Tailwind `hidden` is the cheapest mount-preserving toggle.
       */}
      <div
        className={clsx(
          'flex-1 flex-col',
          tab === 'chat' ? 'flex' : 'hidden',
        )}
      >
        <MessageList
          messages={messages}
          threadId={threadId}
          awaitingApproval={awaitingApproval}
          onApprove={onApprove}
          onDeny={onDeny}
          approvalErrorMessage={approvalErrorMessage}
        />
        <ChatInput
          onSend={onSend}
          disabled={inputDisabled}
          placeholder={placeholder}
        />
      </div>
      <div
        className={clsx(
          'flex-1 flex-col',
          tab === 'dashboard' ? 'flex' : 'hidden',
        )}
      >
        <DashboardView />
      </div>
    </div>
  );
}

function TabButton({
  active,
  onClick,
  label,
}: {
  active: boolean;
  onClick: () => void;
  label: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={clsx(
        'rounded px-4 py-1 text-sm font-semibold',
        active
          ? 'bg-blue-600 text-white'
          : 'bg-white text-gray-700 hover:bg-gray-100',
      )}
    >
      {label}
    </button>
  );
}
