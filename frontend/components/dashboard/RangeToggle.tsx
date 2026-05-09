'use client';
import clsx from 'clsx';
import { RANGE_OPTIONS } from '@/lib/constants';

interface Props {
  selectedDays: number;
  onChange: (days: number) => void;
}

/**
 * D-15.1 segmented control: 7d | 30d | 90d.
 * Active state uses the LOCKED accent (bg-blue-600 text-white per UI-SPEC §Color).
 * No-op on already-active click — onChange only fires for an actual selection change.
 */
export function RangeToggle({ selectedDays, onChange }: Props) {
  return (
    <div role="radiogroup" aria-label="Time range" className="flex gap-1">
      {RANGE_OPTIONS.map((opt) => {
        const active = opt.days === selectedDays;
        return (
          <button
            key={opt.label}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => {
              if (!active) onChange(opt.days);
            }}
            className={clsx(
              'rounded border px-3 py-1 text-sm font-normal',
              active
                ? 'border-blue-600 bg-blue-600 text-white brand-gradient shadow-sm shadow-brand-from/30'
                : 'border-white/15 bg-white text-gray-700 hover:bg-gray-50 glass-surface text-text-secondary hover:bg-white/10',
            )}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}
