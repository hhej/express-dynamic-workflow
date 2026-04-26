/**
 * Display formatters for surcharge UI. All formatters are pure and
 * deterministic so component snapshots stay stable across runs.
 *
 * Date formatting uses Intl.RelativeTimeFormat (browser-native) — we
 * deliberately avoid date-fns/dayjs to keep the bundle lean.
 */

/** Format a THB amount as e.g. "152.50 THB". */
export function formatTHB(amount: number): string {
  const rounded = Math.round(amount * 100) / 100;
  return `${rounded.toFixed(2)} THB`;
}

/** Format a fraction (0.0187) as "1.87%". */
export function formatPercent(fraction: number, decimals = 2): string {
  return `${(fraction * 100).toFixed(decimals)}%`;
}

/** Render an ISO-8601 timestamp as a relative phrase ("2 minutes ago"). */
export function formatRelativeTime(isoTimestamp: string, nowMs = Date.now()): string {
  const then = Date.parse(isoTimestamp);
  if (Number.isNaN(then)) return isoTimestamp;
  const diffSec = Math.round((then - nowMs) / 1000);
  const rtf = new Intl.RelativeTimeFormat('en', { numeric: 'auto' });
  const abs = Math.abs(diffSec);
  if (abs < 60) return rtf.format(diffSec, 'second');
  if (abs < 3600) return rtf.format(Math.round(diffSec / 60), 'minute');
  if (abs < 86_400) return rtf.format(Math.round(diffSec / 3600), 'hour');
  return rtf.format(Math.round(diffSec / 86_400), 'day');
}
