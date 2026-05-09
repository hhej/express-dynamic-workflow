'use client';
import { useConversations } from '@/hooks/useConversations';
import { ThreadListItem } from '@/components/sidebar/ThreadListItem';

interface Props {
  activeThreadId: string | null;
  onResume: (threadId: string) => void;
  onNewConversation: () => void;
}

export function ConversationSidebar({
  activeThreadId,
  onResume,
  onNewConversation,
}: Props) {
  const { items, loading } = useConversations();

  return (
    <aside className="flex w-64 flex-col gap-3 border-r border-white/10 glass-panel p-4 text-text-primary">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold">Conversations</h2>
      </div>
      <button
        type="button"
        onClick={onNewConversation}
        className="rounded bg-blue-600 brand-gradient px-3 py-2 text-sm font-semibold text-white shadow-md shadow-brand-from/30 hover:brightness-110"
      >
        + New conversation
      </button>
      {loading ? (
        <p className="text-xs text-text-muted">Loading…</p>
      ) : items.length === 0 ? (
        <p className="text-sm font-normal text-text-secondary">
          No conversations yet. Send a message to start.
        </p>
      ) : (
        <ul className="flex flex-col gap-2 overflow-y-auto">
          {items.map((item) => (
            <ThreadListItem
              key={item.thread_id}
              item={item}
              active={item.thread_id === activeThreadId}
              onClick={onResume}
            />
          ))}
        </ul>
      )}
    </aside>
  );
}
