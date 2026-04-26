import type { SSEEvent } from '@/types/agent.types';

/**
 * Parse a fetch Response carrying SSE frames. Calls `onEvent` for each
 * parsed event. Returns when the stream ends or `signal` aborts.
 *
 * Backend frame shape: `data: <json>\n\n` (one event per double-newline).
 * Designed for POST /api/chat (EventSource is GET-only).
 *
 * Buffers across chunk boundaries so a frame split mid-JSON across two
 * `read()` results is reassembled before parsing (Pitfall 7 mitigation).
 *
 * Malformed JSON frames are logged via `console.error` and skipped — the
 * stream continues so a single bad frame cannot poison the whole turn.
 *
 * @param response - fetch Response with a readable body
 * @param onEvent  - callback invoked for each parsed SSEEvent
 * @param signal   - optional AbortSignal; cancels the reader cleanly
 */
export async function parseSseStream(
  response: Response,
  onEvent: (event: SSEEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  if (!response.body) throw new Error('SSE response has no body');
  const reader = response.body.getReader();
  const decoder = new TextDecoder('utf-8');
  let buffer = '';

  try {
    while (true) {
      if (signal?.aborted) {
        await reader.cancel();
        return;
      }
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      let boundary: number;
      while ((boundary = buffer.indexOf('\n\n')) !== -1) {
        const frame = buffer.slice(0, boundary);
        buffer = buffer.slice(boundary + 2);
        const line = frame.startsWith('data:') ? frame.slice(5).trim() : frame.trim();
        if (!line) continue;
        try {
          onEvent(JSON.parse(line) as SSEEvent);
        } catch (err) {
          console.error('[sse] failed to parse frame', line, err);
        }
      }
    }
  } finally {
    reader.releaseLock();
  }
}
