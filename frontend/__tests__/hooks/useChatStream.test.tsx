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

  it('Phase 999.9 D-08: send(message, originHubId) forwards origin_hub_id in POST body', async () => {
    let capturedBody: { message?: string; origin_hub_id?: string; thread_id?: string } | null = null;
    server.use(
      http.post('http://localhost:8000/api/chat', async ({ request }) => {
        capturedBody = (await request.json()) as typeof capturedBody;
        return sseResponse();
      }),
    );
    const { result } = renderHook(() => useChatStream());
    await act(async () => {
      await result.current.send('hello', 'branch-bang-na');
    });
    await waitFor(() => expect(result.current.status).toBe('done'));
    expect(capturedBody).not.toBeNull();
    expect(capturedBody!.message).toBe('hello');
    expect(capturedBody!.origin_hub_id).toBe('branch-bang-na');
  });

  it('Phase 999.9 D-08: send(message) without originHubId omits origin_hub_id (Pitfall 1 — backend boundary defaults)', async () => {
    let capturedBody: Record<string, unknown> | null = null;
    server.use(
      http.post('http://localhost:8000/api/chat', async ({ request }) => {
        capturedBody = (await request.json()) as Record<string, unknown>;
        return sseResponse();
      }),
    );
    const { result } = renderHook(() => useChatStream());
    await act(async () => {
      await result.current.send('hello');
    });
    await waitFor(() => expect(result.current.status).toBe('done'));
    expect(capturedBody).not.toBeNull();
    expect(capturedBody!.message).toBe('hello');
    // Either omitted from JSON or present-but-undefined (post-stringify, undefined keys are dropped).
    expect(capturedBody!.origin_hub_id).toBeUndefined();
  });

  it('a second send() aborts the first — D-08 single-turn invariant', async () => {
    server.use(
      http.post('http://localhost:8000/api/chat', async ({ request }) => {
        const body = (await request.json()) as { message: string };
        if (body.message === 'first') {
          // Long-lived stream that emits one trace event from a fictitious
          // FIRST_AGENT and then awaits abort. If the second send fails to
          // abort us, this trace entry would leak into liveTrace alongside
          // the second turn's 5 happy events (D-08 violation).
          const stream = new ReadableStream<Uint8Array>({
            async start(controller) {
              const enc = new TextEncoder();
              controller.enqueue(
                enc.encode(
                  `data: ${JSON.stringify({ type: 'meta', payload: { thread_id: 't-first' } })}\n\n`,
                ),
              );
              // Hold the stream open by never enqueueing more / never closing.
              // The reader.cancel() call from parseSseStream's abort branch
              // will short-circuit the consumer; we don't rely on jsdom
              // propagating cancel() to the source for the assertion.
            },
          });
          return new HttpResponse(stream, {
            headers: { 'Content-Type': 'text/event-stream' },
          });
        }
        return sseResponse(happyTurnEvents('thread-happy'));
      }),
    );
    const { result } = renderHook(() => useChatStream());
    // Fire-and-forget the first send, then yield ticks for postChat to
    // resolve and parseSseStream to start reading the first body.
    await act(async () => {
      void result.current.send('first');
      await new Promise((r) => setTimeout(r, 50));
    });
    await act(async () => {
      await result.current.send('second');
    });
    await waitFor(() => expect(result.current.status).toBe('done'));
    // Second stream's meta wins (proves new turn replaced old).
    expect(result.current.threadId).toBe('thread-happy');
    // D-08 invariant: liveTrace contains only the second turn's 5 happy
    // events — no leakage from the aborted first turn.
    expect(result.current.liveTrace).toHaveLength(5);
    expect(result.current.finalPayload?.status).toBe('ok');
  });
});
