/**
 * Agent-level types: TraceEntry, SurchargeResult, FinalPayload, SSEEvent.
 * Verified field-for-field against backend/agent/nodes/*.py and
 * backend/agent/nodes/response_node.py. snake_case is intentional.
 */

/** AgentName extended with hitl_gate + search_agent (Plan 05-04 / 05-05). */
export type AgentName =
  | 'planner'
  | 'fuel_agent'
  | 'route_agent'
  | 'pricing_agent'
  | 'response'
  | 'hitl_gate' // Plan 05-05
  | 'search_agent'; // Plan 05-04

export type TraceStatus = 'ok' | 'warn' | 'error';

/** 12-field trace record emitted by every backend agent node. */
export interface TraceEntry {
  step: number;
  agent: AgentName;
  tool: string | null;
  tool_input: Record<string, unknown>;
  tool_output: Record<string, unknown>;
  reasoning: string;
  timestamp: string; // ISO-8601 UTC with 'Z'
  status: TraceStatus;
}

/** Mirrors backend response_node._render_table SurchargeResult shape. */
export interface SurchargeResult {
  surcharge_pct: number; // fraction, e.g., 0.10 = 10%
  surcharge_amount: number; // THB
  total: number; // THB
  capped: boolean;
}

export type FinalStatus = 'ok' | 'partial' | 'clarify';

/** One source row inside a SearchContext (Plan 05-04). */
export interface SearchContextSource {
  title: string;
  url: string;
  snippet: string;
  published_at: string | null;
}

/** Search context payload from response_node when search_agent ran (D-11). */
export interface SearchContext {
  query: string;
  summary: string | null;
  sources: SearchContextSource[];
  fetched_at: string;
}

/** Mirrors backend AgentState.final_payload built by response_node. */
export interface FinalPayload {
  markdown: string;
  /**
   * Phase 7 D-01/D-04 — REQUIRED. Backend stamps `'{thread_id}-{turn_idx}'`
   * on every answer payload at backend/api/routes/chat.py::_drain_events.
   * The frontend reads this verbatim into ChatMessage.id and forwards it to
   * POST /api/feedback. NEVER reconstruct this string on the FE side
   * (audit Issue 3 root cause).
   */
  message_id: string;
  surcharge_result: SurchargeResult | null;
  capped: boolean;
  status: FinalStatus;
  /** Plan 05-04 — populated when search_agent ran on this turn. */
  search_context?: SearchContext | null;
}

/** Approval payload from the sixth SSE event (Plan 05-05). */
export interface ApprovalPayload {
  thread_id: string;
  surcharge_result: SurchargeResult;
  threshold: number;
}

/** SSE envelope — 6 event types after Plan 05-05. */
export type SSEEvent =
  | { type: 'meta'; payload: { thread_id: string } }
  | { type: 'trace'; payload: TraceEntry }
  | { type: 'answer'; payload: FinalPayload }
  | { type: 'error'; payload: { message: string; retryable: boolean } }
  | { type: 'done'; payload: Record<string, never> }
  | { type: 'approval_required'; payload: ApprovalPayload };
