/**
 * TypeScript mirror of backend/api/models.py.
 * Field names are intentionally snake_case to match the JSON wire format.
 * DO NOT rename — backend serialization is the source of truth.
 */

/** POST /api/chat request body. Mirrors backend ChatRequest. */
export interface ChatRequest {
  message?: string;
  thread_id?: string;
  /** Plan 05-05 D-06: HITL resume decision; pair with thread_id, omit message. */
  approve?: boolean;
}

/** Item in `GET /api/conversations` array. Mirrors backend ConversationSummary. */
export interface ConversationSummary {
  thread_id: string;
  last_updated: string;
  first_message_preview: string;
}

/** Item in `GET /api/fuel-prices?days=N` array. Mirrors backend FuelPricePoint. */
export interface FuelPricePoint {
  date: string;
  price: number;
  unit: string;
  source: string;
}

/** Replayed message from `GET /api/conversations/:id`. */
export interface ReplayedMessage {
  role: string;
  content: string;
}

/** `GET /api/conversations/:id` response shape. */
export interface ConversationDetail {
  thread_id: string;
  messages: ReplayedMessage[];
  surcharge_result: import('./agent.types').SurchargeResult | null;
  reasoning_trace: import('./agent.types').TraceEntry[];
  fuel_data: Record<string, unknown> | null;
  route_data: Record<string, unknown> | null;
  errors: Array<Record<string, unknown>>;
}
