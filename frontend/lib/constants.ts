/** Public env var, falls back to localhost for unit tests/dev. */
export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000';

/** D-09 demo seed prompts — copy LOCKED by UI-SPEC §Copywriting. */
export const EXAMPLE_PROMPTS = [
  'Surcharge for 15kg Bounce, Bangkok → Nonthaburi',
  'What about Retail Fast?',
  '30kg Retail Standard, Bangkok → Pathum Thani',
] as const;

/** D-15.1 fuel-price chart range options. Default = 30d. */
export const RANGE_OPTIONS = [
  { label: '7d', days: 7 },
  { label: '30d', days: 30 },
  { label: '90d', days: 90 },
] as const;

export const DEFAULT_RANGE_DAYS = 30;

/** localStorage key registry. Keep all keys here so they're easy to audit/reset. */
export const LOCAL_STORAGE_KEYS = {
  threadId: 'thread_id',
  feedback: 'feedback',
} as const;

/** D-15.2 surcharge-history walks the most recent N threads. */
export const SURCHARGE_HISTORY_LIMIT = 20;
