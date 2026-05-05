import { describe, expect, it } from 'vitest';
import { makeSseStream, happyTurnEvents } from '../fixtures/sse';

describe('makeSseStream (test infra smoke)', () => {
  it('produces a closeable ReadableStream of well-formed SSE frames', async () => {
    const events = happyTurnEvents();
    const stream = makeSseStream(events);
    const reader = stream.getReader();
    const decoder = new TextDecoder();
    let raw = '';
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      raw += decoder.decode(value, { stream: true });
    }
    // First frame must be the meta event.
    expect(raw.startsWith('data: ')).toBe(true);
    expect(raw).toContain('"type":"meta"');
    expect(raw).toContain('"type":"answer"');
    expect(raw).toContain('"type":"done"');
    // Frame separator must be \n\n (Pitfall 10 invariant).
    expect(raw.split('\n\n').length).toBeGreaterThanOrEqual(events.length);
  });
});
