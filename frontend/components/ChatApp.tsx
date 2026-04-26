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

  // When a finalPayload arrives, append it as an assistant message and
  // refresh the sidebar so the new (or updated) thread shows up.
  useEffect(() => {
    if (!chat.finalPayload) return;
    if (chat.status !== 'done') return;
    if (lastAppendedPayloadRef.current === chat.finalPayload) return;
    lastAppendedPayloadRef.current = chat.finalPayload;
    setMessages((prev) => [
      ...prev,
      {
        role: 'assistant',
        id: `a-${Date.now()}`,
        payload: chat.finalPayload as FinalPayload,
      },
    ]);
    void conversations.refresh();
  }, [chat.finalPayload, chat.status, conversations]);

  const handleSend = useCallback(
    (message: string) => {
      setMessages((prev) => [...prev, { role: 'user', content: message }]);
      void chat.send(message);
    },
    [chat],
  );

  const handleResume = useCallback(
    async (threadId: string) => {
      try {
        const detail = await conversations.resume(threadId);
        // Replay prior messages into the chat surface. The backend returns
        // role + content text only; assistant messages get wrapped in a
        // minimal FinalPayload so MessageList's renderer keeps working.
        const replayed: ChatMessage[] = detail.messages.map((m, i) => {
          if (m.role === 'assistant') {
            const payload: FinalPayload = {
              markdown: m.content,
              surcharge_result: detail.surcharge_result,
              capped: detail.surcharge_result?.capped ?? false,
              status: 'ok',
            };
            return { role: 'assistant', id: `replay-${i}`, payload };
          }
          return { role: 'user', content: m.content };
        });
        setMessages(replayed);
        // Reset the appended-payload guard so the NEXT real `done` payload
        // (from a follow-up send) is correctly appended even if the resume
        // happened to leave the previous finalPayload in chat state.
        lastAppendedPayloadRef.current = null;
      } catch (err) {
        console.error('[resume]', err);
      }
    },
    [conversations],
  );

  const handleNewConversation = useCallback(() => {
    chat.reset();
    setMessages([]);
    lastAppendedPayloadRef.current = null;
  }, [chat]);

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
        isStreaming={chat.status === 'streaming'}
        onSend={handleSend}
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
