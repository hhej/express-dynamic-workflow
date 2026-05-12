'use client';
import { useState } from 'react';
import { TraceStatusBadge } from '@/components/trace/TraceStatusBadge';
import type { AgentName, TraceEntry } from '@/types/agent.types';

/** D-07: agent display labels. Plan 06-01 D-01: extended with hitl_gate + search_agent (Plan 05-05 / 05-04). */
const AGENT_LABEL: Record<AgentName, string> = {
  planner: 'Planner',
  fuel_agent: 'Fuel agent',
  route_agent: 'Route agent',
  pricing_agent: 'Pricing agent',
  response: 'Response',
  hitl_gate: 'Approval gate',
  search_agent: 'Search agent',
};

interface Props {
  entry: TraceEntry;
}

export function TraceStep({ entry }: Props) {
  const [open, setOpen] = useState(false);
  return (
    <li className="rounded glass-surface">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-sm"
      >
        <span className="flex min-w-0 items-center gap-2">
          <span className="font-mono text-xs text-text-muted">#{entry.step}</span>
          <span className="font-semibold">{AGENT_LABEL[entry.agent]}</span>
          <span className="truncate text-text-secondary">{entry.reasoning}</span>
        </span>
        <TraceStatusBadge status={entry.status} />
      </button>
      {open && (
        <div className="space-y-2 border-t border-white/10 px-3 py-2 text-xs text-text-secondary">
          {entry.tool && (
            <div>
              <span className="font-semibold">Tool:</span>{' '}
              <code className="font-mono">{entry.tool}</code>
            </div>
          )}
          <div>
            <div className="font-semibold">Input</div>
            <pre className="overflow-x-auto rounded bg-white/5 p-2 font-mono text-text-primary">
              {JSON.stringify(entry.tool_input, null, 2)}
            </pre>
          </div>
          <div>
            <div className="font-semibold">Output</div>
            <pre className="overflow-x-auto rounded bg-white/5 p-2 font-mono text-text-primary">
              {JSON.stringify(entry.tool_output, null, 2)}
            </pre>
          </div>
          <div className="text-text-muted">
            <time dateTime={entry.timestamp} title={entry.timestamp}>
              {entry.timestamp}
            </time>
          </div>
        </div>
      )}
    </li>
  );
}
