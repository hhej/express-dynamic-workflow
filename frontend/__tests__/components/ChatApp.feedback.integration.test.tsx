import { describe, expect, it, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { ChatApp } from '@/components/ChatApp';
import { server } from '../mocks/server';
import { HAPPY_PAYLOAD, HAPPY_TRACE, makeSseStream } from '../fixtures/sse';
import type { SSEEvent } from '@/types/agent.types';

/**
 * Phase 7 D-09 + D-11 — Vitest+MSW round-trip integration tests for the
 * feedback contract.
 *
 * The audit's Issue 3 root cause was that the FE constructed assistant
 * message ids as `a-${Date.now()}` (e.g. "a-1714706402381") which the
 * backend regex `^(.+)-(\d+)$` parsed as thread_id="a", turn_idx=1714706402381,
 * mismatching `body.thread_id` and 400-ing every production thumbs click.
 * Phase 7 fixed the contract by stamping message_id on the BE
 * (Plan 07-01) and reading it on the FE (Plan 07-02).
 *
 * These tests are the lasting drift-prevention layer:
 *   D-09 (live):  Render ChatApp, send a query, click thumbs-up,
 *                 assert POST /api/feedback fires with a message_id
 *                 that parses through the BE regex AND whose parsed
 *                 thread_id equals body.thread_id.
 *   D-11 (resume): Mock GET /api/conversations/:id, trigger handleResume,
 *                  click thumbs-up on the replayed last assistant,
 *                  assert POST /api/feedback uses the BE-supplied
 *                  message_id (the same string the BE attached to the
 *                  assistant message).
 */

beforeEach(() => {
  window.localStorage.clear();
});

describe('ChatApp feedback integration (Phase 7 D-09 + D-11)', () => {
  it('D-09 live path: thumbs-up POST /api/feedback fires with BE-stamped message_id that parses through `^(.+)-(\\d+)$` and matches body.thread_id', async () => {
    const user = userEvent.setup();
    const THREAD_ID = 'a4b27c8e-d4f1-4ddd-aaaa-1234567890ab';
    const MESSAGE_ID = `${THREAD_ID}-0`;

    const happyEvents: SSEEvent[] = [
      { type: 'meta', payload: { thread_id: THREAD_ID } },
      ...HAPPY_TRACE.map((entry) => ({
        type: 'trace' as const,
        payload: entry,
      })),
      {
        type: 'answer',
        payload: { ...HAPPY_PAYLOAD, message_id: MESSAGE_ID },
      },
      { type: 'done', payload: {} },
    ];

    let feedbackBody: {
      thread_id: string;
      message_id: string;
      score: string;
    } | null = null;

    server.use(
      http.post(
        'http://localhost:8000/api/chat',
        () =>
          new HttpResponse(makeSseStream(happyEvents), {
            headers: { 'Content-Type': 'text/event-stream' },
          }),
      ),
      http.post(
        'http://localhost:8000/api/feedback',
        async ({ request }) => {
          feedbackBody = (await request.json()) as typeof feedbackBody;
          // Defensive in-test assertions: the wire body MUST satisfy the BE contract.
          expect(feedbackBody!.message_id).toMatch(/^(.+)-(\d+)$/);
          const m = feedbackBody!.message_id.match(/^(.+)-(\d+)$/)!;
          expect(m[1]).toBe(feedbackBody!.thread_id);
          return HttpResponse.json({
            status: 'ok',
            delivered: true,
            trace_id: 'fake-trace',
          });
        },
      ),
    );

    render(<ChatApp />);

    await waitFor(() =>
      expect(
        screen.getByRole('button', { name: 'Send message' }),
      ).toBeInTheDocument(),
    );

    await user.type(
      screen.getByPlaceholderText(/Ask about a surcharge/),
      'Surcharge for 15kg Bounce Bangkok to Nonthaburi',
    );
    await user.click(screen.getByRole('button', { name: 'Send message' }));

    // Wait for answer to render (table appears).
    await waitFor(
      () => expect(screen.getByRole('table')).toBeInTheDocument(),
      { timeout: 4000 },
    );

    // Click thumbs-up.
    await user.click(screen.getByRole('button', { name: 'Helpful' }));

    // Verify POST /api/feedback fired with the BE-stamped message_id.
    await waitFor(() => expect(feedbackBody).not.toBeNull());
    expect(feedbackBody!).toEqual({
      thread_id: THREAD_ID,
      message_id: MESSAGE_ID,
      score: 'up',
    });
  });

  it('D-11 resume path: handleResume reads m.message_id from GET /api/conversations/:id, thumbs-up POST /api/feedback uses that BE-supplied id', async () => {
    const user = userEvent.setup();
    const RESUME_THREAD_ID = 'replay-thread';
    // Concrete BE-shape message_id literal: 'replay-thread-0' (per Phase 7
    // D-01/D-02 stamping convention `{thread_id}-{turn_idx}`).
    const RESUME_MESSAGE_ID = 'replay-thread-0';

    // Mock the conversation list (sidebar) so the resume thread shows up.
    server.use(
      http.get('http://localhost:8000/api/conversations', () =>
        HttpResponse.json([
          {
            thread_id: RESUME_THREAD_ID,
            last_updated: '2026-05-04T00:00:00Z',
            first_message_preview: 'Surcharge for 15kg Bounce…',
          },
        ]),
      ),
      // Mock the per-thread fetch with messages carrying message_id on the LAST assistant only.
      http.get(
        `http://localhost:8000/api/conversations/${RESUME_THREAD_ID}`,
        () =>
          HttpResponse.json({
            thread_id: RESUME_THREAD_ID,
            messages: [
              {
                role: 'user',
                content: 'Surcharge for 15kg Bounce Bangkok to Nonthaburi',
              },
              {
                role: 'assistant',
                content: HAPPY_PAYLOAD.markdown,
                message_id: RESUME_MESSAGE_ID,
              },
            ],
            surcharge_result: HAPPY_PAYLOAD.surcharge_result,
            reasoning_trace: [],
            fuel_data: null,
            route_data: null,
            errors: [],
          }),
      ),
    );

    let feedbackBody: {
      thread_id: string;
      message_id: string;
      score: string;
    } | null = null;

    server.use(
      http.post(
        'http://localhost:8000/api/feedback',
        async ({ request }) => {
          feedbackBody = (await request.json()) as typeof feedbackBody;
          return HttpResponse.json({
            status: 'ok',
            delivered: true,
            trace_id: 'fake-trace',
          });
        },
      ),
    );

    render(<ChatApp />);

    // Wait for sidebar to populate, then click the conversation entry to trigger handleResume.
    // ThreadListItem renders each conversation as a button with aria-label
    // "Resume <preview> — last updated <relative>".
    const resumeButton = await screen.findByRole(
      'button',
      { name: /Resume Surcharge for 15kg Bounce/ },
      { timeout: 4000 },
    );
    await user.click(resumeButton);

    // Wait for the replayed assistant message's table to render
    // (HAPPY_PAYLOAD.markdown contains a markdown table).
    await waitFor(
      () => expect(screen.getByRole('table')).toBeInTheDocument(),
      { timeout: 4000 },
    );

    // Click thumbs-up on the replayed last-assistant message.
    await user.click(screen.getByRole('button', { name: 'Helpful' }));

    // Verify POST /api/feedback fired with the BE-supplied message_id (NOT 'replay-0').
    await waitFor(() => expect(feedbackBody).not.toBeNull());
    expect(feedbackBody!).toEqual({
      thread_id: RESUME_THREAD_ID,
      message_id: RESUME_MESSAGE_ID,
      score: 'up',
    });
  });
});
