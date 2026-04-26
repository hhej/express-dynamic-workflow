import clsx from 'clsx';
import type { TraceStatus } from '@/types/agent.types';

/** UI-SPEC §Color — LOCKED status palette. Do not change without updating UI-SPEC. */
const STATUS_COLOR: Record<TraceStatus | 'running', string> = {
  ok: 'bg-green-100 text-green-800',
  warn: 'bg-yellow-100 text-yellow-800',
  error: 'bg-red-100 text-red-800',
  running: 'bg-gray-100 text-gray-700 animate-pulse',
};

interface Props {
  status: TraceStatus | 'running';
}

export function TraceStatusBadge({ status }: Props) {
  return (
    <span
      className={clsx(
        'rounded px-2 py-0.5 text-xs font-medium',
        STATUS_COLOR[status],
      )}
    >
      {status}
    </span>
  );
}
