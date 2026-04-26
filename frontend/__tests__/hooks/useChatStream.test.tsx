import { describe, expect, it, beforeEach } from 'vitest';
import { act, renderHook, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { useChatStream } from '@/hooks/useChatStream';
import { server } from '../mocks/server';
import { happyTurnEvents, makeSseStream } from '../fixtures/sse';
import { LOCAL_STORAGE_KEYS } from '@/lib/constants';
import type { SSEEvent } from '@/types/agent.types';

function sseResponse(events: SSEEvent[] = happyTurnEvents()) {
  return new HttpResponse(makeSseStream(events), {
    headers: { 'Content-Type': 'text/event-stream' },
  });
}

beforeEach(() => {
  window.localStorage.clear();
});

describe('useChatStream', () => {
  it('dispatches META → TRACE × 5 → ANSWER → DONE on a happy stream', async () => {
    server.use(http.post('http://localhost:8000/api/chat', () => sseResponse()));
    const { result } = renderHook(() => useChatStream());
    await act(async () => {
      await result.current.send('hi');
    });
    await waitFor(() => expect(result.current.status).toBe('done'));
    expect(result.current.liveTrace).toHaveLength(5);
    expect(result.current.finalPayload?.status).toBe('ok');
    expect(result.current.threadId).toBe('thread-happy');
  });

  it('persists thread_id from meta event to localStorage', async () => {
    server.use(http.post('http://localhost:8000/api/chat', () => sseResponse()));
    const { result } = renderHook(() => useChatStream());
    await act(async () => {
      await result.current.send('hi');
    });
    await waitFor(() =>
      expect(window.localStorage.getItem(LOCAL_STORAGE_KEYS.threadId)).toBe('thread-happy'),
    );
  });

  it('reset() clears thread_id from localStorage and zeroes liveTrace', async () => {
    server.use(http.post('http://localhost:8000/api/chat', () => sseResponse()));
    const { result } = renderHook(() => useChatStream());
    await act(async () => {
      await result.current.send('hi');
    });
    await waitFor(() => expect(result.current.liveTrace.length).toBeGreaterThan(0));
    act(() => result.current.reset());
    expect(result.current.liveTrace).toHaveLength(0);
    expect(window.localStorage.getItem(LOCAL_STORAGE_KEYS.threadId)).toBeNull();
    expect(result.current.threadId).toBeNull();
  });

  it('surfaces SSE error event into state.error and status="error"', async () => {
    server.use(
      http.post('http://localhost:8000/api/chat', () =>
        sseResponse([
          { type: 'meta', payload: { thread_id: 't' } },
          { type: 'error', payload: { message: 'tool failed', retryable: true } },
          { type: 'done', payload: {} },
        ]),
      ),
    );
    const { result } = renderHook(() => useChatStream());
    await act(async () => {
      await result.current.send('hi');
    });
    await waitFor(() => expect(result.current.status).toBe('error'));
    expect(result.current.error?.message).toBe('tool failed');
    expect(result.current.error?.retryable).toBe(true);
  });

  it('a second send() aborts the first — D-08 single-turn invariant', async () => {
    let firstAborted = false;
    server.use(
      http.post('http://localhost:8000/api/chat', async ({ request }) => {
        const body = (await request.json()) as { message: string };
        const events: SSEEvent[] =
          body.message === 'first'
            ? [{ type: 'meta', payload: { thread_id: 't1' } }]
            : happyTurnEvents('thread-happy');
        const stream = new ReadableStream<Uint8Array>({
          start(controller) {
            const enc = new TextEncoder();
            for (const ev of events) {
              controller.enqueue(enc.encode(`data: ${JSON.stringify(ev)}\n\n`));
            }
            if (body.message !== 'first') controller.close();
            // For 'first', leave open until aborted.
          },
          cancel() {
            firstAborted = true;
          },
        });
        return new HttpResponse(stream, {
          headers: { 'Content-Type': 'text/event-stream' },
        });
      }),
    );
    const { result } = renderHook(() => useChatStream());
    await act(async () => {
      void result.current.send('first');
    });
    await act(async () => {
      await result.current.send('second');
    });
    await waitFor(() => expect(result.current.status).toBe('done'));
    expect(result.current.threadId).toBe('thread-happy'); // second stream's meta wins
    expect(firstAborted).toBe(true);
  });
});
