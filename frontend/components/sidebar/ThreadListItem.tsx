'use client';
import clsx from 'clsx';
import { formatRelativeTime } from '@/lib/formatters';
import type { ConversationSummary } from '@/types/api.types';

interface Props {
  item: ConversationSummary;
  active: boolean;
  onClick: (threadId: string) => void;
}

export function ThreadListItem({ item, active, onClick }: Props) {
  const relative = formatRelativeTime(item.last_updated);
  const preview = item.first_message_preview || '(no preview)';
  return (
    <li>
      <button
        type="button"
        onClick={() => onClick(item.thread_id)}
        aria-label={`Resume ${preview} — last updated ${relative}`}
        aria-current={active ? 'true' : undefined}
        className={clsx(
          'flex w-full flex-col items-start gap-1 rounded px-3 py-2 text-left text-sm',
          active
            ? 'bg-blue-600 text-white brand-gradient shadow-sm shadow-brand-from/30'
            : 'glass-surface text-text-primary hover:bg-white/10',
        )}
      >
        <span className="line-clamp-2 font-normal">{preview}</span>
        <span
          className={clsx(
            'text-xs',
            active ? 'text-blue-100' : 'text-text-muted',
          )}
        >
          {relative}
        </span>
      </button>
    </li>
  );
}
