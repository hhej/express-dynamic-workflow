import { describe, expect, it, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { ChatApp } from '@/components/ChatApp';
import { server } from '../mocks/server';
import {
  HAPPY_PAYLOAD,
  HAPPY_TRACE,
  PARTIAL_PAYLOAD,
  makeSseStream,
  happyTurnEvents,
} from '../fixtures/sse';
import type { ApprovalPayload, SSEEvent } from '@/types/agent.types';

/**
 * Plan 06-03 D-15.3 — End-to-end HITL approve + deny integration test.
 *
 * The audit's lesson (Issue 2) was that every layer passed its own unit
 * tests but the full ChatApp → ChatColumn → MessageList → ApprovalCard
 * prop chain was never exercised end-to-end. This test renders the
 * production ChatApp and walks the full SSE happy + deny paths through
 * MSW so any future regression that drops chat.approve or
 * chat.approvalPayload re-introduces the same bug AND fails this test.
 */

const APPROVAL_PAYLOAD: ApprovalPayload = {
  thread_id: 'thread-hitl',
  surcharge_result: HAPPY_PAYLOAD.surcharge_result!,
  threshold: 100,
};

/** Initial fresh-turn SSE: meta → 4 traces (no response trace yet) → approval_required (NO done — Pitfall 2). */
function pausedTurnEvents(): SSEEvent[] {
  return [
    { type: 'meta', payload: { thread_id: 'thread-hitl' } },
    ...HAPPY_TRACE.slice(0, 4).map((entry) => ({
      type: 'trace' as const,
      payload: entry,
    })),
    { type: 'approval_required', payload: APPROVAL_PAYLOAD },
  ];
}

/** Resume SSE for approve: meta → response trace → answer (HAPPY_PAYLOAD) → done. */
function approveResumeEvents(): SSEEvent[] {
  return [
    { type: 'meta', payload: { thread_id: 'thread-hitl' } },
    { type: 'trace', payload: HAPPY_TRACE[4] },
    { type: 'answer', payload: HAPPY_PAYLOAD },
    { type: 'done', payload: {} },
  ];
}

/** Resume SSE for deny: meta → response trace → answer (PARTIAL_PAYLOAD) → done. */
function denyResumeEvents(): SSEEvent[] {
  return [
    { type: 'meta', payload: { thread_id: 'thread-hitl' } },
    {
      type: 'trace',
      payload: { ...HAPPY_TRACE[4], reasoning: 'User declined the surcharge' },
    },
    { type: 'answer', payload: PARTIAL_PAYLOAD },
    { type: 'done', payload: {} },
  ];
}

function sseResponseFromEvents(events: SSEEvent[]) {
  return new HttpResponse(makeSseStream(events), {
    headers: { 'Content-Type': 'text/event-stream' },
  });
}

/**
 * Install a MSW POST /api/chat handler that switches behaviour on each call:
 *   first call (initial send) → pausedTurnEvents
 *   second call (resume)      → resumeEvents
 */
function installPauseThenResumeHandler(resumeEvents: SSEEvent[]) {
  let callCount = 0;
  server.use(
    http.post('http://localhost:8000/api/chat', async ({ request }) => {
      const body = (await request.json()) as {
        message?: string;
        thread_id?: string;
        approve?: boolean;
      };
      callCount += 1;
      if (callCount === 1) {
        // Fresh turn — fire the paused SSE.
        expect(body.message).toBeDefined();
        return sseResponseFromEvents(pausedTurnEvents());
      }
      // Resume turn — must include thread_id + approve.
      expect(body.thread_id).toBe('thread-hitl');
      expect(typeof body.approve).toBe('boolean');
      return sseResponseFromEvents(resumeEvents);
    }),
  );
}

beforeEach(() => {
  window.localStorage.clear();
});

describe('ChatApp HITL integration (D-15.3)', () => {
  it('approve flow: high-value query → ApprovalCard renders → ChatInput disabled with locked placeholder → click Approve → MarkdownAnswer renders final answer', async () => {
    const user = userEvent.setup();
    installPauseThenResumeHandler(approveResumeEvents());
    render(<ChatApp />);

    // Wait for initial mount.
    await waitFor(() =>
      expect(
        screen.getByRole('button', { name: 'Send message' }),
      ).toBeInTheDocument(),
    );

    // Send a high-value query.
    await user.type(
      screen.getByPlaceholderText(/Ask about a surcharge/),
      'expensive shipment that breaches the approval threshold',
    );
    await user.click(screen.getByRole('button', { name: 'Send message' }));

    // ApprovalCard heading appears once SSE emits approval_required.
    await waitFor(
      () =>
        expect(screen.getByText('Approval required')).toBeInTheDocument(),
      { timeout: 4000 },
    );

    // ChatInput is locked while awaiting_approval (Phase 6 ROADMAP §SC 5).
    expect(
      screen.getByRole('button', { name: 'Send message' }),
    ).toBeDisabled();

    // ChatInput shows the locked contextual placeholder (D-08).
    expect(
      screen.getByPlaceholderText(
        'Awaiting your approval — use Approve / Deny above',
      ),
    ).toBeInTheDocument();

    // Click Approve — resume POSTs {thread_id, approve: true} (verified inside the handler).
    await user.click(screen.getByRole('button', { name: /Approve/ }));

    // Final answer arrives via MarkdownAnswer — assert table is rendered.
    await waitFor(
      () => expect(screen.getByRole('table')).toBeInTheDocument(),
      { timeout: 4000 },
    );

    // The HAPPY_PAYLOAD's "Total | 152.50 THB" cell renders.
    expect(screen.getByText(/152.50 THB/)).toBeInTheDocument();

    // ChatInput is re-enabled after done. The Send button stays disabled
    // when the textarea is empty (per ChatInput's `disabled || text.trim().length === 0`),
    // so type a follow-up message first to flip out of the empty-text branch
    // and assert the Send button is no longer locked by inputDisabled.
    await user.type(
      screen.getByPlaceholderText(/Ask about a surcharge/),
      'follow-up',
    );
    await waitFor(() =>
      expect(
        screen.getByRole('button', { name: 'Send message' }),
      ).not.toBeDisabled(),
    );
  });

  it('deny flow: high-value query → ApprovalCard renders → click Deny → PartialCard renders with deny prose', async () => {
    const user = userEvent.setup();
    installPauseThenResumeHandler(denyResumeEvents());
    render(<ChatApp />);

    await waitFor(() =>
      expect(
        screen.getByRole('button', { name: 'Send message' }),
      ).toBeInTheDocument(),
    );

    await user.type(
      screen.getByPlaceholderText(/Ask about a surcharge/),
      'expensive shipment that breaches the approval threshold',
    );
    await user.click(screen.getByRole('button', { name: 'Send message' }));

    await waitFor(
      () =>
        expect(screen.getByText('Approval required')).toBeInTheDocument(),
      { timeout: 4000 },
    );

    // Click Deny — resume POSTs {thread_id, approve: false}.
    await user.click(screen.getByRole('button', { name: /Deny/ }));

    // PartialCard renders the PARTIAL_PAYLOAD prose.
    await waitFor(
      () =>
        expect(
          screen.getByText(
            /Limited result — fuel data fetched but route lookup failed/,
          ),
        ).toBeInTheDocument(),
      { timeout: 4000 },
    );

    // ChatInput is re-enabled after done. (Type follow-up text first to clear
    // the empty-text disabled branch — see approve-flow comment above.)
    await user.type(
      screen.getByPlaceholderText(/Ask about a surcharge/),
      'follow-up',
    );
    await waitFor(() =>
      expect(
        screen.getByRole('button', { name: 'Send message' }),
      ).not.toBeDisabled(),
    );
  });
});

/**
 * Phase 8 D-14 — sidebar refresh propagation integration test.
 *
 * Closes audit Issue 4 (`v1.0-MILESTONE-AUDIT.md` §2.3): exercises the
 * production prop chain end-to-end to prove that when ChatApp fires
 * `void conversations.refresh()` on `done`, the new thread appears in
 * ConversationSidebar without a page reload — only possible because
 * useConversations is now a single provider-backed instance shared by
 * all three consumers (ChatApp, ConversationSidebar, SurchargeHistoryChart).
 *
 * If a future regression drops the <ConversationsProvider> wrap or
 * reintroduces per-call-site useState, the sidebar would stay on the
 * empty-state copy and this test would fail.
 */
describe('ChatApp sidebar refresh integration (Phase 8 D-14)', () => {
  it('completed turn appends new thread to ConversationSidebar without page reload (audit Issue 4)', async () => {
    const user = userEvent.setup();

    // Two-call MSW handler: empty list first, then [thread-happy] after refresh.
    let convCallCount = 0;
    server.use(
      http.get('http://localhost:8000/api/conversations', () => {
        convCallCount += 1;
        if (convCallCount === 1) {
          return HttpResponse.json([]);
        }
        return HttpResponse.json([
          {
            thread_id: 'thread-happy',
            last_updated: '2026-05-04T10:00:00Z',
            first_message_preview:
              'Surcharge for 15kg Bounce, Bangkok → Nonthaburi',
          },
        ]);
      }),
      // Fresh-turn happy SSE: meta → 5 traces → answer → done.
      http.post('http://localhost:8000/api/chat', () => {
        const stream = makeSseStream(happyTurnEvents('thread-happy'));
        return new HttpResponse(stream, {
          headers: { 'Content-Type': 'text/event-stream' },
        });
      }),
    );

    render(<ChatApp />);

    // Wait for the first GET /api/conversations to settle (empty list →
    // sidebar's empty-state copy is in the document).
    await waitFor(() =>
      expect(screen.getByText(/No conversations yet/)).toBeInTheDocument(),
    );

    // Send a query — fires SSE turn that completes with `done`.
    await user.type(
      screen.getByPlaceholderText(/Ask about a surcharge/),
      'Surcharge for 15kg Bounce, Bangkok → Nonthaburi',
    );
    await user.click(screen.getByRole('button', { name: 'Send message' }));

    // Wait for the answer's table to render — proves `done` fired and
    // void conversations.refresh() ran in the post-`done` useEffect.
    await waitFor(
      () => expect(screen.getByRole('table')).toBeInTheDocument(),
      { timeout: 4000 },
    );

    // The sidebar now shows the thread WITHOUT a page reload — this only
    // works if useConversations is a single shared provider instance
    // (audit Issue 4 closure). If the sidebar were running its own
    // useState/useEffect, it would still show "No conversations yet".
    // Scope to the sidebar's resume button (aria-label = "Resume <preview>
    // — last updated …") because the answer markdown also contains the
    // preview text — the button-name match disambiguates.
    await waitFor(
      () =>
        expect(
          screen.getByRole('button', {
            name: /Resume Surcharge for 15kg Bounce/,
          }),
        ).toBeInTheDocument(),
      { timeout: 4000 },
    );

    // Exactly two GET /api/conversations calls: provider mount + post-`done` refresh.
    // (Pitfall 3 — useMemo on context value AND deps narrowing on conversations.refresh
    // together prevent unbounded refetches.)
    expect(convCallCount).toBe(2);
  });
});
