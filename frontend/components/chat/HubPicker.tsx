'use client';
import clsx from 'clsx';
import type { Hub } from '@/types/agent.types';

interface Props {
  hubs: Hub[];
  value: string;
  onChange: (hubId: string) => void;
  disabled?: boolean;
}

/**
 * Phase 999.9 — Origin hub dropdown (UI-SPEC §Component Inventory).
 *
 * Locked visual contract:
 *   - "From:" label in font-semibold (heading style per UI-SPEC §Typography)
 *   - Native <select> with body-style options (text-sm font-normal)
 *   - glass-surface background, focus ring brand-via/40 (matches ChatInput)
 *   - NO accent fill — HubPicker is intentionally subordinate
 *     (UI-SPEC §Color "Accent reserved-for list — HubPicker is NOT on this list")
 *
 * Locked interaction contract (UI-SPEC §Interaction Contracts):
 *   - Native <select> keyboard semantics (Tab / Space / Enter / arrows)
 *   - <label htmlFor> + aria-label="Origin hub" (defense-in-depth)
 *   - Disabled when chat is streaming or awaiting approval
 *   - <option> text format: `${name} (${zone})` — UI-SPEC §"<option> rendering rule"
 */
export function HubPicker({ hubs, value, onChange, disabled }: Props) {
  return (
    <label
      htmlFor="hub-picker"
      className="flex items-center gap-2 text-sm text-text-primary"
    >
      <span className="font-semibold">From:</span>
      <select
        id="hub-picker"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        aria-label="Origin hub"
        className={clsx(
          'rounded border border-white/15 bg-white/5 backdrop-blur-md px-2 py-1',
          'text-sm font-normal text-text-primary',
          'focus:border-brand-via focus:outline-none focus:ring-2 focus:ring-brand-via/40',
          'disabled:opacity-60',
        )}
      >
        {hubs.map((h) => (
          <option key={h.hub_id} value={h.hub_id}>
            {h.name} ({h.zone})
          </option>
        ))}
      </select>
    </label>
  );
}
