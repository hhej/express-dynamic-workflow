import { http, HttpResponse } from 'msw';
import { happyTurnEvents, makeSseStream } from '../fixtures/sse';
import { SAMPLE_CONVERSATIONS, SAMPLE_FUEL_PRICES } from '../fixtures/agentState';

const API_BASE = 'http://localhost:8000';

export const handlers = [
  http.post(`${API_BASE}/api/chat`, () => {
    const stream = makeSseStream(happyTurnEvents());
    return new HttpResponse(stream, {
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
      },
    });
  }),

  http.get(`${API_BASE}/api/conversations`, () => {
    return HttpResponse.json(SAMPLE_CONVERSATIONS);
  }),

  http.get(`${API_BASE}/api/conversations/:threadId`, ({ params }) => {
    return HttpResponse.json({
      thread_id: params.threadId,
      messages: [
        { role: 'user', content: 'Surcharge for 15kg Bounce, Bangkok → Nonthaburi' },
        { role: 'assistant', content: 'Total 152.50 THB' },
      ],
      surcharge_result: {
        surcharge_pct: 0.0187,
        surcharge_amount: 2.5,
        total: 152.5,
        capped: false,
      },
      reasoning_trace: [],
      fuel_data: null,
      route_data: null,
      errors: [],
    });
  }),

  http.get(`${API_BASE}/api/fuel-prices`, () => {
    return HttpResponse.json(SAMPLE_FUEL_PRICES);
  }),
];
