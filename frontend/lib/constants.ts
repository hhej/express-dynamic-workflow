/** Public env var, falls back to localhost for unit tests/dev. */
export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:8000';

/**
 * Demo seed prompts (Phase 999.9). Six prompts cover all 3 shipping
 * types, the HQ/Branch hub model, the HITL approval gate, and the
 * fuel-trend (news_query) path:
 *   1. bounce, light, no prose origin → HubPicker / HQ-default path
 *   2. retail_standard, mid weight, full prose, central-1 → central-1
 *   3. bounce, prose origin override, central-2 → central-1 (cross-zone)
 *   4. retail_fast, mid weight, central-1 → central-3 (no HITL)
 *   5. retail_fast, heavy, central-1 → central-3 → triggers HITL
 *      approval gate (total > HITL_TOTAL_THB_THRESHOLD = 500 THB)
 *   6. fuel-trend market query → planner emits news_query and routes
 *      to the search_agent (no surcharge calc)
 */
export const EXAMPLE_PROMPTS = [
  'Surcharge for 5kg Bounce to Nonthaburi',
  '15kg Retail Standard from Bang Na to Pathum Thani',
  '10kg Bounce from Ayutthaya to Nonthaburi',
  '15kg Retail Fast from Samut Prakan to Lop Buri',
  '60kg Retail Fast from Lat Krabang to Ratchaburi',
  'How are diesel prices trending?',
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

/** Phase 999.9 D-08 — sessionStorage key for HubPicker persistence (per browser tab). */
export const HUB_PICKER_STORAGE_KEY = 'express_origin_hub_id';

/** Phase 999.9 D-08 — cold-start default hub. */
export const DEFAULT_HUB_ID = 'hq-lat-krabang';
