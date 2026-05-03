import { describe, it, expect, beforeEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { server } from '../mocks/server';
import { useChatStream } from '@/hooks/useChatStream';
import { API_BASE_URL } from '@/lib/constants';

/**
 * Plan 05-06 — extends Phase 4 useChatStream tests with the sixth SSE event
 * (approval_required) and the new approve(threadId, decision) callback.
 */
describe('useChatStream — approval_required handling (Plan 05-06)', () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it('flips status to awaiting_approval when approval_required event arrives', async () => {
    // Stream a meta + approval_required event, then close (no done — Pitfall 2).
    server.use(
      http.post(`${API_BASE_URL}/api/chat`, () => {
        const stream = new ReadableStream({
          start(controller) {
            controller.enqueue(
              new TextEncoder().encode(
                'data: {"type":"meta","payload":{"thread_id":"t-1"}}\n\n',
              ),
            );
            controller.enqueue(
              new TextEncoder().encode(
                'data: {"type":"approval_required","payload":{"thread_id":"t-1","surcharge_result":{"surcharge_pct":0.1,"surcharge_amount":65,"total":715,"capped":false},"threshold":500}}\n\n',
              ),
            );
            controller.close();
          },
        });
        return new HttpResponse(stream, {
          headers: { 'Content-Type': 'text/event-stream' },
        });
      }),
    );
    const { result } = renderHook(() => useChatStream());
    await act(async () => {
      await result.current.send('expensive shipment');
    });
    await waitFor(() =>
      expect(result.current.status).toBe('awaiting_approval'),
    );
    expect(result.current.approvalPayload?.surcharge_result.total).toBe(715);
    expect(result.current.approvalPayload?.threshold).toBe(500);
  });

  it('approve(threadId, true) POSTs {thread_id, approve: true} and resumes streaming', async () => {
    let captured: { thread_id?: string; approve?: boolean } = {};
    server.use(
      http.post(`${API_BASE_URL}/api/chat`, async ({ request }) => {
        const body = (await request.json()) as {
          thread_id?: string;
          approve?: boolean;
        };
        captured = { thread_id: body.thread_id, approve: body.approve };
        const stream = new ReadableStream({
          start(controller) {
            controller.enqueue(
              new TextEncoder().encode(
                'data: {"type":"meta","payload":{"thread_id":"t-1"}}\n\n',
              ),
            );
            controller.enqueue(
              new TextEncoder().encode(
                'data: {"type":"answer","payload":{"markdown":"ok","status":"ok","surcharge_result":null,"capped":false}}\n\n',
              ),
            );
            controller.enqueue(
              new TextEncoder().encode(
                'data: {"type":"done","payload":{}}\n\n',
              ),
            );
            controller.close();
          },
        });
        return new HttpResponse(stream, {
          headers: { 'Content-Type': 'text/event-stream' },
        });
      }),
    );
    const { result } = renderHook(() => useChatStream());
    await act(async () => {
      await result.current.approve('t-1', true);
    });
    expect(captured.thread_id).toBe('t-1');
    expect(captured.approve).toBe(true);
    await waitFor(() => expect(result.current.status).toBe('done'));
  });

  it('approve(threadId, false) POSTs approve: false', async () => {
    let captured: { approve?: boolean } = {};
    server.use(
      http.post(`${API_BASE_URL}/api/chat`, async ({ request }) => {
        const body = (await request.json()) as { approve?: boolean };
        captured = { approve: body.approve };
        const stream = new ReadableStream({
          start(controller) {
            controller.enqueue(
              new TextEncoder().encode(
                'data: {"type":"done","payload":{}}\n\n',
              ),
            );
            controller.close();
          },
        });
        return new HttpResponse(stream, {
          headers: { 'Content-Type': 'text/event-stream' },
        });
      }),
    );
    const { result } = renderHook(() => useChatStream());
    await act(async () => {
      await result.current.approve('t-1', false);
    });
    expect(captured.approve).toBe(false);
  });

  it('approve resume failure flips status to error', async () => {
    server.use(
      http.post(`${API_BASE_URL}/api/chat`, () => HttpResponse.error()),
    );
    const { result } = renderHook(() => useChatStream());
    await act(async () => {
      await result.current.approve('t-1', true);
    });
    await waitFor(() => expect(result.current.status).toBe('error'));
  });
});
