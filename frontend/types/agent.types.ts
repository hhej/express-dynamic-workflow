/**
 * Agent-level types: TraceEntry, SurchargeResult, FinalPayload, SSEEvent.
 * Verified field-for-field against backend/agent/nodes/*.py and
 * backend/agent/nodes/response_node.py. snake_case is intentional.
 */

export type AgentName =
  | 'planner'
  | 'fuel_agent'
  | 'route_agent'
  | 'pricing_agent'
  | 'response';

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

/** Mirrors backend AgentState.final_payload built by response_node. */
export interface FinalPayload {
  markdown: string;
  surcharge_result: SurchargeResult | null;
  capped: boolean;
  status: FinalStatus;
}

/** SSE envelope — 5 event types per Phase 3 D-18. */
export type SSEEvent =
  | { type: 'meta'; payload: { thread_id: string } }
  | { type: 'trace'; payload: TraceEntry }
  | { type: 'answer'; payload: FinalPayload }
  | { type: 'error'; payload: { message: string; retryable: boolean } }
  | { type: 'done'; payload: Record<string, never> };
