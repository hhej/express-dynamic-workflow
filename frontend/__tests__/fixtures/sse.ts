import type { SSEEvent, TraceEntry, FinalPayload } from '@/types/agent.types';

/**
 * Build a ReadableStream<Uint8Array> of SSE frames matching the backend
 * format `data: <json>\n\n`. Closes the controller after enqueuing all
 * events so the reader doesn't deadlock (Pitfall 10).
 */
export function makeSseStream(events: SSEEvent[]): ReadableStream<Uint8Array> {
  const enc = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      for (const ev of events) {
        controller.enqueue(enc.encode(`data: ${JSON.stringify(ev)}\n\n`));
      }
      controller.close();
    },
  });
}

const TIMESTAMP = '2026-04-26T10:15:30.000Z';

/** Canonical "happy path" trace: planner -> fuel -> route -> pricing -> response. */
export const HAPPY_TRACE: TraceEntry[] = [
  {
    step: 1,
    agent: 'planner',
    tool: null,
    tool_input: {},
    tool_output: { next_step: 'fetch_fuel' },
    reasoning: 'Routing to fuel agent',
    timestamp: TIMESTAMP,
    status: 'ok',
  },
  {
    step: 2,
    agent: 'fuel_agent',
    tool: 'fetch_fuel_price',
    tool_input: {},
    tool_output: { price: 30.5, baseline: 29.94, delta_pct: 0.0187 },
    reasoning: 'Diesel up 1.87% vs baseline',
    timestamp: TIMESTAMP,
    status: 'ok',
  },
  {
    step: 3,
    agent: 'route_agent',
    tool: 'calculate_route',
    tool_input: { origin: 'Bangkok', destination: 'Nonthaburi' },
    tool_output: { distance_km: 18, zone: 'central-1' },
    reasoning: 'Zone central-1 confirmed',
    timestamp: TIMESTAMP,
    status: 'ok',
  },
  {
    step: 4,
    agent: 'pricing_agent',
    tool: 'calculate_surcharge',
    tool_input: { weight_kg: 15 },
    tool_output: { surcharge_pct: 0.0187, total: 152.5 },
    reasoning: 'Surcharge 1.87%, total 152.50 THB',
    timestamp: TIMESTAMP,
    status: 'ok',
  },
  {
    step: 5,
    agent: 'response',
    tool: null,
    tool_input: {},
    tool_output: {},
    reasoning: 'Rendered final markdown',
    timestamp: TIMESTAMP,
    status: 'ok',
  },
];

export const HAPPY_PAYLOAD: FinalPayload = {
  status: 'ok',
  capped: false,
  surcharge_result: {
    surcharge_pct: 0.0187,
    surcharge_amount: 2.5,
    total: 152.5,
    capped: false,
  },
  markdown:
    'Surcharge for 15kg Bounce, Bangkok → Nonthaburi.\n\n| Item | Value |\n|---|---|\n| Base rate | 150.00 THB |\n| Surcharge % | 1.87% |\n| Surcharge | 2.50 THB |\n| Total | 152.50 THB |\n',
};

export const CAPPED_PAYLOAD: FinalPayload = {
  status: 'ok',
  capped: true,
  surcharge_result: {
    surcharge_pct: 0.15,
    surcharge_amount: 22.5,
    total: 172.5,
    capped: true,
  },
  markdown:
    '> ⚠ Cap/floor applied — review recommended\n\nSurcharge for 15kg Bounce, Bangkok → Nonthaburi.\n\n| Item | Value |\n|---|---|\n| Base rate | 150.00 THB |\n| Surcharge % | 15.00% |\n| Surcharge | 22.50 THB |\n| Total | 172.50 THB |\n',
};

export const CLARIFY_PAYLOAD: FinalPayload = {
  status: 'clarify',
  capped: false,
  surcharge_result: null,
  markdown: 'I need a bit more info. Please share weight, origin, and destination.',
};

export const PARTIAL_PAYLOAD: FinalPayload = {
  status: 'partial',
  capped: false,
  surcharge_result: null,
  markdown: 'Limited result — fuel data fetched but route lookup failed.',
};

/** Build a complete SSE event sequence for a happy turn. */
export function happyTurnEvents(threadId = 'thread-happy'): SSEEvent[] {
  return [
    { type: 'meta', payload: { thread_id: threadId } },
    ...HAPPY_TRACE.map((entry) => ({ type: 'trace' as const, payload: entry })),
    { type: 'answer', payload: HAPPY_PAYLOAD },
    { type: 'done', payload: {} },
  ];
}
