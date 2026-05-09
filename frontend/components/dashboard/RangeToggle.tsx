'use client';
import clsx from 'clsx';
import { RANGE_OPTIONS } from '@/lib/constants';

interface Props {
  selectedDays: number;
  onChange: (days: number) => void;
}

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
              'rounded-md px-3 py-1 text-sm font-medium transition-colors',
              active
                ? 'brand-gradient text-white shadow-sm shadow-brand-from/30'
                : 'glass-surface text-text-primary hover:bg-white/15 hover:text-white',
            )}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}
