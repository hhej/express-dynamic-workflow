'use client';
import { useCallback, useEffect, useRef, useState } from 'react';
import { ChatColumn } from '@/components/chat/ChatColumn';
import { ConversationSidebar } from '@/components/sidebar/ConversationSidebar';
import { TracePanel } from '@/components/trace/TracePanel';
import { useChatStream } from '@/hooks/useChatStream';
import { ConversationsProvider, useConversations } from '@/hooks/useConversations';
import hubsData from '@/data/hubs.json';
import { HUB_PICKER_STORAGE_KEY, DEFAULT_HUB_ID } from '@/lib/constants';
import type { ChatMessage } from '@/components/chat/MessageList';
import type { FinalPayload, Hub } from '@/types/agent.types';

// Phase 999.9 D-08 — module-level constant; static-import is build-time
// resolved so the array is stable across renders without useMemo.
const HUBS_LIST: Hub[] = Object.entries(hubsData).map(
  ([hub_id, data]) => ({
    hub_id,
    ...(data as Omit<Hub, 'hub_id'>),
  }),
);
const HUB_ID_ALLOWLIST = new Set(HUBS_LIST.map((h) => h.hub_id));

/**
 * Top-level Client Component composing the three-column desktop layout
 * (sidebar | chat | trace). Owns the chat message history and bridges:
 *
 *   - useChatStream → ChatColumn (status, send, threadId) and TracePanel (liveTrace, isStreaming)
 *   - useConversations → ConversationSidebar (items, resume, refresh)
 *
 * D-01 layout, D-04 tab toggle (delegated to ChatColumn), D-05 mobile
 * collapse (sidebar + trace panel are `hidden md:flex`), D-14 + D-20
 * resume → next-turn thread continuity, D-08 single-turn liveTrace.
 */
function ChatAppInner() {
  const chat = useChatStream();
  const conversations = useConversations();
  const [messages, setMessages] = useState<ChatMessage[]>([]);

  // Phase 999.9 D-08 — lifted originHubId state. Cold render uses
  // DEFAULT_HUB_ID; the post-hydration useEffect below seeds from
  // sessionStorage if a valid hub_id is stored (RESEARCH Pitfall 6 —
  // avoid SSR hydration mismatch by reading sessionStorage in an effect,
  // not in the initial useState).
  const [originHubId, setOriginHubId] = useState<string>(DEFAULT_HUB_ID);

  // Phase 999.9 D-08 / RESEARCH Pitfall 6 — post-hydration sessionStorage
  // read avoids SSR mismatch. Cold render uses DEFAULT_HUB_ID; this
  // effect runs once after mount and overrides if sessionStorage holds
  // a valid hub_id. Invalid stored values fall through (allowlist guard).
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const stored = window.sessionStorage.getItem(HUB_PICKER_STORAGE_KEY);
    if (stored && HUB_ID_ALLOWLIST.has(stored)) {
      setOriginHubId(stored);
    }
  }, []);

  // Phase 999.9 D-08 — persist every change to sessionStorage so the
  // picker survives cross-route navigation within the same tab.
  // sessionStorage scope: per browser tab; closes with the tab.
  useEffect(() => {
    if (typeof window === 'undefined') return;
    window.sessionStorage.setItem(HUB_PICKER_STORAGE_KEY, originHubId);
  }, [originHubId]);

  const handleHubChange = useCallback((hubId: string) => {
    setOriginHubId(hubId);
  }, []);

  // Track the finalPayload we've already appended so a re-render after `done`
  // doesn't double-append the same assistant message.
  const lastAppendedPayloadRef = useRef<FinalPayload | null>(null);
  // Plan 06-02 D-06: ref guards the placeholder pending-assistant slot so it
  // is appended at most once per HITL pause window (re-renders during the
  // awaiting_approval status do not re-push the placeholder).
  const pendingApprovalSlotRef = useRef<boolean>(false);

  // When a finalPayload arrives, append it as an assistant message and
  // refresh the sidebar so the new (or updated) thread shows up.
  //
  // Debug 999.5 (2026-05-09): dep array narrowed from
  // `[chat.finalPayload, chat.status, conversations.refresh]` to
  // `[chat.finalPayload, chat.status]`. `conversations.refresh` is
  // stable today (useCallback with [] deps), but listing it as a dep
  // gives the effect an extra re-fire vector if a future refactor
  // destabilises the reference. The effect doesn't read .refresh's
  // identity for control flow — it just CALLS it as a side effect —
  // so dropping it from deps is correctness-preserving and removes a
  // future-foot-gun. Pair this with the handleResume guard-seed below
  // (belt-and-braces against the `done` effect re-appending the prior
  // turn's finalPayload onto a freshly replayed history).
  useEffect(() => {
    if (!chat.finalPayload) return;
    if (chat.status !== 'done') return;
    if (lastAppendedPayloadRef.current === chat.finalPayload) return;
    lastAppendedPayloadRef.current = chat.finalPayload;
    setMessages((prev) => {
      // Plan 06-02 D-06: if a placeholder pending assistant slot was appended
      // for HITL, replace it with the real payload so the placeholder id
      // (`pending-${ts}`) never persists into history (Phase 7 will rewrite
      // assistant message ids — the strip-and-replace path keeps the
      // placeholder from leaking into that contract).
      const stripped =
        pendingApprovalSlotRef.current &&
        prev.length > 0 &&
        prev[prev.length - 1].role === 'assistant' &&
        (prev[prev.length - 1] as { payload: FinalPayload | null }).payload ===
          null
          ? prev.slice(0, -1)
          : prev;
      pendingApprovalSlotRef.current = false;
      return [
        ...stripped,
        {
          role: 'assistant',
          // Phase 7 D-03: BE-stamped message_id from FinalPayload (replaces
          // a-${Date.now()} clock-derived id — audit Issue 3 root cause).
          // Single source of truth: backend builds the string at
          // backend/api/routes/chat.py::_drain_events and the frontend reads
          // it verbatim. NEVER reconstruct on the FE side.
          id: chat.finalPayload!.message_id,
          payload: chat.finalPayload as FinalPayload,
        },
      ];
    });
    void conversations.refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- conversations.refresh
    // is intentionally omitted (see comment above): it is stable today and
    // the effect only invokes it as a side effect.
  }, [chat.finalPayload, chat.status]);

  // Plan 06-02 D-06: when SSE emits approval_required, append a placeholder
  // assistant message whose null payload is the slot ApprovalCard hangs off
  // (MessageList renders ApprovalCard in the last assistant slot when
  // awaitingApproval is set).
  useEffect(() => {
    if (chat.status !== 'awaiting_approval') return;
    if (pendingApprovalSlotRef.current) return;
    pendingApprovalSlotRef.current = true;
    setMessages((prev) => [
      ...prev,
      {
        role: 'assistant',
        id: `pending-${Date.now()}`,
        payload: null,
      },
    ]);
  }, [chat.status]);

  const handleSend = useCallback(
    (message: string) => {
      setMessages((prev) => [...prev, { role: 'user', content: message }]);
      // Phase 999.9 D-08 — forward originHubId so backend receives the
      // user's chosen hub on every turn (or the default 'hq-lat-krabang').
      void chat.send(message, originHubId);
    },
    [chat, originHubId],
  );

  // Plan 06-02 D-03: thin handler callbacks consume chat.approve so the
  // ApprovalCard buttons (rendered three layers down) only need synchronous
  // void-returning handlers.
  const handleApprove = useCallback(() => {
    if (!chat.threadId) return;
    void chat.approve(chat.threadId, true);
  }, [chat]);

  const handleDeny = useCallback(() => {
    if (!chat.threadId) return;
    void chat.approve(chat.threadId, false);
  }, [chat]);

  const handleResume = useCallback(
    async (threadId: string) => {
      try {
        const detail = await conversations.resume(threadId);
        // Replay prior messages into the chat surface. The backend returns
        // role + content text only; assistant messages get wrapped in a
        // minimal FinalPayload so MessageList's renderer keeps working.
        const replayed: ChatMessage[] = detail.messages.map((m, i) => {
          if (m.role === 'assistant') {
            // Phase 7 D-05: BE attaches message_id to the LAST assistant of each
            // turn (see backend/api/routes/conversations.py::_attach_message_ids).
            // Earlier in-turn assistants (HITL pre-pause partials) get no field —
            // we propagate the absence into payload.message_id (empty string)
            // so the MessageList feedback-button gate (Task 3 / D-08) suppresses
            // FeedbackButtons on non-canonical rows.
            const payload: FinalPayload = {
              markdown: m.content,
              surcharge_result: detail.surcharge_result,
              capped: detail.surcharge_result?.capped ?? false,
              status: 'ok',
              message_id: m.message_id ?? '',
            };
            return {
              role: 'assistant',
              // Use BE-supplied id when present; fall back to a synthetic
              // non-canonical id for non-last in-turn assistant rows so React's
              // reconciliation key stays stable (FeedbackButtons won't render
              // anyway because payload.message_id is empty — Task 3 gate).
              id: m.message_id ?? `replay-noncanonical-${i}`,
              payload,
            };
          }
          return { role: 'user', content: m.content };
        });
        setMessages(replayed);
        // Phase 7 Rule 2 / D-11: propagate the resumed thread_id into
        // chat state so the MessageList feedback-button gate (threadId
        // truthy) fires on replayed messages. Before Phase 7 chat.threadId
        // stayed null after a resume click and feedback was silently
        // broken on every resumed conversation.
        // Debug 999.5 (2026-05-09): seed the appended-payload guard with
        // the CURRENT finalPayload (the last turn's already-appended payload)
        // BEFORE chat.setThreadId() runs the RESET reducer that clears it.
        // RESET clears chat.finalPayload to null, so the `done` effect's
        // `if (!chat.finalPayload) return;` check normally short-circuits
        // post-resume. The guard seed is belt-and-braces: if a future change
        // ever lets the effect re-evaluate with the OLD finalPayload still
        // visible (e.g., a render scheduled before RESET took effect), the
        // ref-equality guard `lastAppendedPayloadRef.current === finalPayload`
        // short-circuits BEFORE the duplicate append fires. setting null
        // (the previous behaviour) ARMED the guard for re-fire — the guard
        // failed when it mattered. Seeding the live identity disarms it.
        //
        // For a follow-up `send()` after this resume, useChatStream.send()
        // dispatches START which recreates state with finalPayload=null;
        // the next ANSWER produces a brand-new payload object identity, so
        // the seed (which references the prior turn's payload, possibly null)
        // does not block that legitimate append.
        lastAppendedPayloadRef.current = chat.finalPayload;
        chat.setThreadId(threadId);
      } catch (err) {
        console.error('[resume]', err);
      }
    },
    [conversations, chat],
  );

  const handleNewConversation = useCallback(() => {
    chat.reset();
    setMessages([]);
    lastAppendedPayloadRef.current = null;
    // Plan 06-02 D-06: also clear the pending slot guard so a "+ New
    // conversation" click during a paused HITL turn cleanly resets state.
    pendingApprovalSlotRef.current = false;
  }, [chat]);

  // Plan 06-02 D-07: inputDisabled true while streaming OR awaiting approval.
  const inputDisabled =
    chat.status === 'streaming' || chat.status === 'awaiting_approval';
  // Plan 06-02 D-08: contextual placeholder during HITL pause.
  const placeholder =
    chat.status === 'awaiting_approval'
      ? 'Awaiting your approval — use Approve / Deny above'
      : undefined;
  // Plan 06-02 D-13: surface error message to ApprovalCard when an
  // approve/deny POST failed AND we are still in the awaiting-approval window.
  const approvalErrorMessage =
    chat.status === 'error' && chat.approvalPayload
      ? chat.error?.message ?? 'Could not send your decision — try again.'
      : null;

  return (
    <main className="flex h-screen w-screen overflow-hidden bg-transparent text-text-primary">
      <div className="hidden md:flex">
        <ConversationSidebar
          activeThreadId={chat.threadId}
          onResume={(tid) => void handleResume(tid)}
          onNewConversation={handleNewConversation}
        />
      </div>
      <ChatColumn
        messages={messages}
        threadId={chat.threadId}
        inputDisabled={inputDisabled}
        onSend={handleSend}
        awaitingApproval={chat.approvalPayload}
        onApprove={handleApprove}
        onDeny={handleDeny}
        approvalErrorMessage={approvalErrorMessage}
        placeholder={placeholder}
        hubs={HUBS_LIST}
        originHubId={originHubId}
        onHubChange={handleHubChange}
      />
      <div className="hidden md:flex">
        <TracePanel
          entries={chat.liveTrace}
          isStreaming={chat.status === 'streaming'}
          onExamplePromptClick={handleSend}
        />
      </div>
    </main>
  );
}

/**
 * Phase 8 D-02 — top-level export wraps ChatAppInner with ConversationsProvider
 * so all three consumers (ChatAppInner, ConversationSidebar, SurchargeHistoryChart)
 * read from the same shared instance. Pitfall 1 mitigation: ChatAppInner
 * sits BELOW the provider in the React tree, so its useConversations() call
 * resolves cleanly.
 */
export function ChatApp() {
  return (
    <ConversationsProvider>
      <ChatAppInner />
    </ConversationsProvider>
  );
}
