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
    <aside className="flex w-64 flex-col gap-3 border-r border-gray-200 bg-gray-50 p-4">
      <div className="flex items-center justify-between">
        <h2 className="text-base font-semibold">Conversations</h2>
      </div>
      <button
        type="button"
        onClick={onNewConversation}
        className="rounded bg-blue-600 px-3 py-2 text-sm font-semibold text-white hover:bg-blue-700"
      >
        + New conversation
      </button>
      {loading ? (
        <p className="text-xs text-gray-500">Loading…</p>
      ) : items.length === 0 ? (
        <p className="text-sm font-normal text-gray-700">
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
