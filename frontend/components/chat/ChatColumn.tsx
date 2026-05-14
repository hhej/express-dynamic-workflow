'use client';
import { useState } from 'react';
import clsx from 'clsx';
import { ChatInput } from '@/components/chat/ChatInput';
import { HubPicker } from '@/components/chat/HubPicker';
import { MessageList, type ChatMessage } from '@/components/chat/MessageList';
import { DashboardView } from '@/components/dashboard/DashboardView';
import type { ApprovalPayload, Hub } from '@/types/agent.types';

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
  /** Phase 999.9 D-08 — full hub list rendered in the HubPicker dropdown. */
  hubs: Hub[];
  /** Phase 999.9 D-08 — currently-selected origin hub id. */
  originHubId: string;
  /** Phase 999.9 D-08 — fires when user picks a different hub. */
  onHubChange: (hubId: string) => void;
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
  hubs,
  originHubId,
  onHubChange,
}: Props) {
  const [tab, setTab] = useState<CenterTab>('chat');

  return (
    <div className="flex flex-1 flex-col bg-transparent text-text-primary">
      <div className="flex items-center gap-1 border-b border-white/10 p-2">
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
          'flex-1 flex-col min-h-0',
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
        {/*
          Phase 999.9 — input-row container holds HubPicker (first child)
          and ChatInput (second child). UI-SPEC §Spacing Scale: flex-col gap-2
          + top border + p-4 padding (matches the previous ChatInput <form> p-4
          + border-t pattern, now lifted to the wrapper so HubPicker shares it).
        */}
        <div className="flex flex-col gap-2 border-t border-white/10 p-4">
          <HubPicker
            hubs={hubs}
            value={originHubId}
            onChange={onHubChange}
            disabled={inputDisabled}
          />
          <ChatInput
            onSend={onSend}
            disabled={inputDisabled}
            placeholder={placeholder}
          />
        </div>
      </div>
      <div
        className={clsx(
          'flex-1 flex-col min-h-0',
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
        'rounded-md px-4 py-1 text-sm font-semibold transition-colors',
        active
          ? 'brand-gradient text-white shadow-md shadow-brand-from/30'
          : 'glass-surface text-text-primary hover:bg-white/15 hover:text-white',
      )}
    >
      {label}
    </button>
  );
}
