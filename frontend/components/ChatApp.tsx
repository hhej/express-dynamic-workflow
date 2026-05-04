'use client';
import { useCallback, useEffect, useRef, useState } from 'react';
import { ChatColumn } from '@/components/chat/ChatColumn';
import { ConversationSidebar } from '@/components/sidebar/ConversationSidebar';
import { TracePanel } from '@/components/trace/TracePanel';
import { useChatStream } from '@/hooks/useChatStream';
import { useConversations } from '@/hooks/useConversations';
import type { ChatMessage } from '@/components/chat/MessageList';
import type { FinalPayload } from '@/types/agent.types';

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
export function ChatApp() {
  const chat = useChatStream();
  const conversations = useConversations();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  // Track the finalPayload we've already appended so a re-render after `done`
  // doesn't double-append the same assistant message.
  const lastAppendedPayloadRef = useRef<FinalPayload | null>(null);
  // Plan 06-02 D-06: ref guards the placeholder pending-assistant slot so it
  // is appended at most once per HITL pause window (re-renders during the
  // awaiting_approval status do not re-push the placeholder).
  const pendingApprovalSlotRef = useRef<boolean>(false);

  // When a finalPayload arrives, append it as an assistant message and
  // refresh the sidebar so the new (or updated) thread shows up.
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
  }, [chat.finalPayload, chat.status, conversations]);

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
      void chat.send(message);
    },
    [chat],
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
        chat.setThreadId(threadId);
        // Reset the appended-payload guard so the NEXT real `done` payload
        // (from a follow-up send) is correctly appended even if the resume
        // happened to leave the previous finalPayload in chat state.
        lastAppendedPayloadRef.current = null;
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
    <main className="flex h-screen w-screen overflow-hidden bg-white">
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
