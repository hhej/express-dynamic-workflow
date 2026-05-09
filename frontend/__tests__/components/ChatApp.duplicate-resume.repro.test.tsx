import { describe, expect, it, beforeEach } from 'vitest';
import { StrictMode } from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { ChatApp } from '@/components/ChatApp';
import { server } from '../mocks/server';
import { HAPPY_PAYLOAD, HAPPY_TRACE, makeSseStream } from '../fixtures/sse';
import type { SSEEvent } from '@/types/agent.types';

/**
 * Reproduction test for 999.5 — duplicate assistant row after resume.
 *
 * Scenario A: send → done → click own thread in sidebar → expect ONE table
 * Scenario B: send → done → click different thread → click original → expect ONE table per thread
 */

beforeEach(() => {
  window.localStorage.clear();
});

describe('999.5 reproduction', () => {
  it('A: after `done`, clicking the just-finished thread in the sidebar must NOT duplicate the assistant', async () => {
    const user = userEvent.setup();
    const THREAD_ID = 'aaaa-thread-xxx';
    const MESSAGE_ID = `${THREAD_ID}-0`;

    const happyEvents: SSEEvent[] = [
      { type: 'meta', payload: { thread_id: THREAD_ID } },
      ...HAPPY_TRACE.map((entry) => ({ type: 'trace' as const, payload: entry })),
      { type: 'answer', payload: { ...HAPPY_PAYLOAD, message_id: MESSAGE_ID } },
      { type: 'done', payload: {} },
    ];

    let convListCallCount = 0;
    server.use(
      http.post('http://localhost:8000/api/chat', () =>
        new HttpResponse(makeSseStream(happyEvents), {
          headers: { 'Content-Type': 'text/event-stream' },
        }),
      ),
      http.get('http://localhost:8000/api/conversations', () => {
        convListCallCount += 1;
        if (convListCallCount === 1) {
          return HttpResponse.json([]);
        }
        return HttpResponse.json([
          {
            thread_id: THREAD_ID,
            last_updated: '2026-05-09T10:00:00Z',
            first_message_preview: 'Surcharge for 15kg Bounce…',
          },
        ]);
      }),
      http.get(`http://localhost:8000/api/conversations/${THREAD_ID}`, () =>
        HttpResponse.json({
          thread_id: THREAD_ID,
          messages: [
            {
              role: 'user',
              content: 'Surcharge for 15kg Bounce Bangkok to Nonthaburi',
            },
            {
              role: 'assistant',
              content: HAPPY_PAYLOAD.markdown,
              message_id: MESSAGE_ID,
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

    render(
      <StrictMode>
        <ChatApp />
      </StrictMode>,
    );
    await waitFor(() => screen.getByRole('button', { name: 'Send message' }));

    // Step 1: send a message and wait for done.
    await user.type(
      screen.getByPlaceholderText(/Ask about a surcharge/),
      'Surcharge for 15kg Bounce Bangkok to Nonthaburi',
    );
    await user.click(screen.getByRole('button', { name: 'Send message' }));

    await waitFor(
      () => expect(screen.getByRole('table')).toBeInTheDocument(),
      { timeout: 4000 },
    );

    // Wait for the sidebar refresh to expose the new thread button.
    const resumeButton = await screen.findByRole(
      'button',
      { name: /Resume Surcharge for 15kg Bounce/ },
      { timeout: 4000 },
    );

    // Step 2: click own finished thread in the sidebar.
    await user.click(resumeButton);

    // After resume: there must be exactly ONE assistant table.
    await waitFor(() => {
      const tables = screen.queryAllByRole('table');
      expect(tables).toHaveLength(1);
    });

    // Confirm the assistant <li> count is exactly 1.
    const assistantBubbles = document.querySelectorAll('ol > li.self-start');
    // eslint-disable-next-line no-console
    console.log('Scenario A: assistantBubbles=', assistantBubbles.length, 'tables=', screen.queryAllByRole('table').length);
    expect(assistantBubbles).toHaveLength(1);
  });

  it('B: send → done → click DIFFERENT thread → click original thread back. No duplicate.', async () => {
    const user = userEvent.setup();
    const THREAD_A = 'aaaa-thread-A';
    const THREAD_B = 'bbbb-thread-B';
    const MESSAGE_A = `${THREAD_A}-0`;
    const MESSAGE_B = `${THREAD_B}-0`;

    const happyEvents: SSEEvent[] = [
      { type: 'meta', payload: { thread_id: THREAD_A } },
      ...HAPPY_TRACE.map((entry) => ({ type: 'trace' as const, payload: entry })),
      { type: 'answer', payload: { ...HAPPY_PAYLOAD, message_id: MESSAGE_A } },
      { type: 'done', payload: {} },
    ];

    let convListCallCount = 0;
    server.use(
      http.post('http://localhost:8000/api/chat', () =>
        new HttpResponse(makeSseStream(happyEvents), {
          headers: { 'Content-Type': 'text/event-stream' },
        }),
      ),
      http.get('http://localhost:8000/api/conversations', () => {
        convListCallCount += 1;
        if (convListCallCount === 1) {
          // Initial: only B exists.
          return HttpResponse.json([
            {
              thread_id: THREAD_B,
              last_updated: '2026-05-08T10:00:00Z',
              first_message_preview: 'Older B conversation about diesel',
            },
          ]);
        }
        // After fresh send: A is now newest, B follows.
        return HttpResponse.json([
          {
            thread_id: THREAD_A,
            last_updated: '2026-05-09T10:00:00Z',
            first_message_preview: 'Surcharge for 15kg Bounce…',
          },
          {
            thread_id: THREAD_B,
            last_updated: '2026-05-08T10:00:00Z',
            first_message_preview: 'Older B conversation about diesel',
          },
        ]);
      }),
      http.get(`http://localhost:8000/api/conversations/${THREAD_A}`, () =>
        HttpResponse.json({
          thread_id: THREAD_A,
          messages: [
            { role: 'user', content: 'Surcharge for 15kg Bounce' },
            {
              role: 'assistant',
              content: HAPPY_PAYLOAD.markdown,
              message_id: MESSAGE_A,
            },
          ],
          surcharge_result: HAPPY_PAYLOAD.surcharge_result,
          reasoning_trace: [],
          fuel_data: null,
          route_data: null,
          errors: [],
        }),
      ),
      http.get(`http://localhost:8000/api/conversations/${THREAD_B}`, () =>
        HttpResponse.json({
          thread_id: THREAD_B,
          messages: [
            { role: 'user', content: 'Older B conversation about diesel' },
            {
              role: 'assistant',
              content: 'Diesel was 35 THB last week.',
              message_id: MESSAGE_B,
            },
          ],
          surcharge_result: null,
          reasoning_trace: [],
          fuel_data: null,
          route_data: null,
          errors: [],
        }),
      ),
    );

    render(
      <StrictMode>
        <ChatApp />
      </StrictMode>,
    );
    await waitFor(() => screen.getByRole('button', { name: 'Send message' }));

    // Step 1: send a message in thread A.
    await user.type(
      screen.getByPlaceholderText(/Ask about a surcharge/),
      'Surcharge for 15kg Bounce',
    );
    await user.click(screen.getByRole('button', { name: 'Send message' }));

    await waitFor(
      () => expect(screen.getByRole('table')).toBeInTheDocument(),
      { timeout: 4000 },
    );

    // Step 2: click thread B (the OTHER, older thread) in sidebar.
    const threadBButton = await screen.findByRole(
      'button',
      { name: /Resume Older B conversation about diesel/ },
      { timeout: 4000 },
    );
    await user.click(threadBButton);

    // Verify B's prose appears.
    await waitFor(() =>
      expect(screen.getByText(/Diesel was 35 THB last week/)).toBeInTheDocument(),
    );

    // Verify A's table is NOT visible.
    expect(screen.queryByRole('table')).toBeNull();

    // Step 3: click thread A back.
    const threadAButton = screen.getByRole('button', {
      name: /Resume Surcharge for 15kg Bounce/,
    });
    await user.click(threadAButton);

    // Verify A's table is back.
    await waitFor(() => expect(screen.getByRole('table')).toBeInTheDocument());

    // Crucially: only ONE table must be present (no duplicate row).
    const tables = screen.queryAllByRole('table');
    expect(tables).toHaveLength(1);

    // Assistant bubble count: exactly 1.
    const assistantBubbles = document.querySelectorAll('ol > li.self-start');
    expect(assistantBubbles).toHaveLength(1);
  });

  it('C: send → done → click own thread → send a FOLLOW-UP. No duplicate.', async () => {
    const user = userEvent.setup();
    const THREAD_ID = 'cccc-thread-C';
    const MESSAGE_0 = `${THREAD_ID}-0`;
    const MESSAGE_1 = `${THREAD_ID}-1`;

    let chatPostCount = 0;
    const turn0Events: SSEEvent[] = [
      { type: 'meta', payload: { thread_id: THREAD_ID } },
      ...HAPPY_TRACE.map((entry) => ({ type: 'trace' as const, payload: entry })),
      { type: 'answer', payload: { ...HAPPY_PAYLOAD, message_id: MESSAGE_0 } },
      { type: 'done', payload: {} },
    ];
    const turn1Events: SSEEvent[] = [
      { type: 'meta', payload: { thread_id: THREAD_ID } },
      ...HAPPY_TRACE.map((entry) => ({ type: 'trace' as const, payload: entry })),
      {
        type: 'answer',
        payload: {
          ...HAPPY_PAYLOAD,
          message_id: MESSAGE_1,
          markdown: HAPPY_PAYLOAD.markdown + '\n\nFollow-up answer.',
        },
      },
      { type: 'done', payload: {} },
    ];

    server.use(
      http.post('http://localhost:8000/api/chat', () => {
        chatPostCount += 1;
        const events = chatPostCount === 1 ? turn0Events : turn1Events;
        return new HttpResponse(makeSseStream(events), {
          headers: { 'Content-Type': 'text/event-stream' },
        });
      }),
      http.get('http://localhost:8000/api/conversations', () =>
        HttpResponse.json([
          {
            thread_id: THREAD_ID,
            last_updated: '2026-05-09T10:00:00Z',
            first_message_preview: 'Initial Q',
          },
        ]),
      ),
      http.get(`http://localhost:8000/api/conversations/${THREAD_ID}`, () =>
        HttpResponse.json({
          thread_id: THREAD_ID,
          messages: [
            { role: 'user', content: 'Initial Q' },
            {
              role: 'assistant',
              content: HAPPY_PAYLOAD.markdown,
              message_id: MESSAGE_0,
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

    render(<ChatApp />);
    await waitFor(() => screen.getByRole('button', { name: 'Send message' }));

    // Step 1: send turn 0.
    await user.type(
      screen.getByPlaceholderText(/Ask about a surcharge/),
      'Initial Q',
    );
    await user.click(screen.getByRole('button', { name: 'Send message' }));

    await waitFor(
      () => expect(screen.getByRole('table')).toBeInTheDocument(),
      { timeout: 4000 },
    );

    // Step 2: click own thread in sidebar (resume).
    const resumeButton = await screen.findByRole(
      'button',
      { name: /Resume Initial Q/ },
      { timeout: 4000 },
    );
    await user.click(resumeButton);

    // Verify exactly 1 assistant after resume.
    await waitFor(() => {
      expect(screen.queryAllByRole('table')).toHaveLength(1);
    });

    // Step 3: send a follow-up (turn 1) AFTER resume.
    await user.type(
      screen.getByPlaceholderText(/Ask about a surcharge/),
      'Follow-up Q',
    );
    await user.click(screen.getByRole('button', { name: 'Send message' }));

    // Wait for the follow-up answer.
    await waitFor(
      () => expect(screen.getByText(/Follow-up answer\./)).toBeInTheDocument(),
      { timeout: 4000 },
    );

    // After follow-up: exactly 2 assistant bubbles.
    const assistantBubbles = document.querySelectorAll('ol > li.self-start');
    expect(assistantBubbles).toHaveLength(2);
  });
});
