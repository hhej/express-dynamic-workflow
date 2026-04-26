import { describe, expect, it, vi } from 'vitest';
import { parseSseStream } from '@/lib/sse';
import { happyTurnEvents, makeSseStream } from '../fixtures/sse';
import type { SSEEvent } from '@/types/agent.types';

function streamToResponse(stream: ReadableStream<Uint8Array>): Response {
  return new Response(stream, { headers: { 'Content-Type': 'text/event-stream' } });
}

describe('parseSseStream', () => {
  it('calls onEvent for each event in order from a happy-path stream', async () => {
    const events = happyTurnEvents();
    const received: SSEEvent[] = [];
    await parseSseStream(streamToResponse(makeSseStream(events)), (ev) => {
      received.push(ev);
    });
    expect(received).toHaveLength(events.length);
    expect(received[0].type).toBe('meta');
    expect(received[received.length - 1].type).toBe('done');
  });

  it('handles a frame split across two chunks at an arbitrary byte', async () => {
    const enc = new TextEncoder();
    const fullFrame = `data: ${JSON.stringify({ type: 'done', payload: {} })}\n\n`;
    const split = Math.floor(fullFrame.length / 2);
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(enc.encode(fullFrame.slice(0, split)));
        controller.enqueue(enc.encode(fullFrame.slice(split)));
        controller.close();
      },
    });
    const received: SSEEvent[] = [];
    await parseSseStream(streamToResponse(stream), (ev) => received.push(ev));
    expect(received).toEqual([{ type: 'done', payload: {} }]);
  });

  it('logs and continues on malformed JSON instead of throwing', async () => {
    const enc = new TextEncoder();
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(enc.encode('data: {not json}\n\n'));
        controller.enqueue(
          enc.encode(`data: ${JSON.stringify({ type: 'done', payload: {} })}\n\n`),
        );
        controller.close();
      },
    });
    const errSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    const received: SSEEvent[] = [];
    await expect(
      parseSseStream(streamToResponse(stream), (ev) => received.push(ev)),
    ).resolves.toBeUndefined();
    expect(received).toEqual([{ type: 'done', payload: {} }]);
    expect(errSpy).toHaveBeenCalled();
    errSpy.mockRestore();
  });

  it('stops cleanly when AbortSignal aborts mid-stream', async () => {
    const enc = new TextEncoder();
    const controller = new AbortController();
    const stream = new ReadableStream<Uint8Array>({
      start(c) {
        c.enqueue(
          enc.encode(`data: ${JSON.stringify({ type: 'meta', payload: { thread_id: 't' } })}\n\n`),
        );
        controller.abort();
        c.enqueue(enc.encode(`data: ${JSON.stringify({ type: 'done', payload: {} })}\n\n`));
        c.close();
      },
    });
    const received: SSEEvent[] = [];
    await parseSseStream(
      streamToResponse(stream),
      (ev) => received.push(ev),
      controller.signal,
    );
    // First event may or may not have been processed before abort; second must NOT.
    expect(received.find((e) => e.type === 'done')).toBeUndefined();
  });
});
