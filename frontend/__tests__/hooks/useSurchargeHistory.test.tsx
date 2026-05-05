import { describe, expect, it } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { http, HttpResponse, delay } from 'msw';
import { useSurchargeHistory } from '@/hooks/useSurchargeHistory';
import { server } from '../mocks/server';
import type { ConversationSummary } from '@/types/api.types';

function makeItems(n: number): ConversationSummary[] {
  return Array.from({ length: n }, (_, i) => ({
    thread_id: `thread-${i + 1}`,
    last_updated: `2026-04-${String(20 + (i % 7)).padStart(2, '0')}T09:00:00.000Z`,
    first_message_preview: `Surcharge query ${i + 1}`,
  }));
}

describe('useSurchargeHistory (D-15.2)', () => {
  it('returns chart-ready points only for threads with surcharge_result', async () => {
    // Default MSW handler returns surcharge_result populated for every thread.
    const items = makeItems(3);
    const { result } = renderHook(() => useSurchargeHistory(items, false));
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.data).toHaveLength(3);
    expect(result.current.data[0]).toMatchObject({
      total: expect.any(Number),
      surcharge_pct: expect.any(Number),
    });
  });

  it('drops threads where surcharge_result is null', async () => {
    let call = 0;
    server.use(
      http.get('http://localhost:8000/api/conversations/:id', () => {
        call += 1;
        return HttpResponse.json({
          thread_id: `thread-${call}`,
          messages: [],
          surcharge_result:
            call % 2 === 0
              ? null
              : { surcharge_pct: 0.05, surcharge_amount: 5, total: 100, capped: false },
          reasoning_trace: [],
          fuel_data: null,
          route_data: null,
          errors: [],
        });
      }),
    );
    const items = makeItems(4);
    const { result } = renderHook(() => useSurchargeHistory(items, false));
    await waitFor(() => expect(result.current.loading).toBe(false));
    // 4 threads, 2 with surcharge_result populated, 2 with null
    expect(result.current.data).toHaveLength(2);
  });

  it('parallelizes via Promise.all — calls are NOT strictly serial', async () => {
    let inFlight = 0;
    let maxInFlight = 0;
    server.use(
      http.get('http://localhost:8000/api/conversations/:id', async () => {
        inFlight += 1;
        maxInFlight = Math.max(maxInFlight, inFlight);
        await delay(20);
        inFlight -= 1;
        return HttpResponse.json({
          thread_id: 't',
          messages: [],
          surcharge_result: {
            surcharge_pct: 0.05,
            surcharge_amount: 5,
            total: 100,
            capped: false,
          },
          reasoning_trace: [],
          fuel_data: null,
          route_data: null,
          errors: [],
        });
      }),
    );
    const items = makeItems(5);
    const { result } = renderHook(() => useSurchargeHistory(items, false));
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(maxInFlight).toBeGreaterThanOrEqual(2); // parallel, not serial (which would max at 1)
  });

  it('a single failed getConversation does not block other threads', async () => {
    let call = 0;
    server.use(
      http.get('http://localhost:8000/api/conversations/:id', () => {
        call += 1;
        if (call === 2) return HttpResponse.json({ error: 'boom' }, { status: 500 });
        return HttpResponse.json({
          thread_id: `t-${call}`,
          messages: [],
          surcharge_result: {
            surcharge_pct: 0.05,
            surcharge_amount: 5,
            total: 100,
            capped: false,
          },
          reasoning_trace: [],
          fuel_data: null,
          route_data: null,
          errors: [],
        });
      }),
    );
    const items = makeItems(3);
    const { result } = renderHook(() => useSurchargeHistory(items, false));
    await waitFor(() => expect(result.current.loading).toBe(false));
    // 3 threads, 1 failed → 2 points, error stays null (per-thread failure swallowed)
    expect(result.current.data).toHaveLength(2);
    expect(result.current.error).toBeNull();
  });
});
