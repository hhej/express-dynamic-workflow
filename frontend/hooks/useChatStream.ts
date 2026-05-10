'use client';
import { useCallback, useEffect, useReducer, useRef } from 'react';
import { api, ApiError } from '@/lib/api';
import { parseSseStream } from '@/lib/sse';
import { LOCAL_STORAGE_KEYS } from '@/lib/constants';
import type {
  ApprovalPayload,
  FinalPayload,
  SSEEvent,
  TraceEntry,
} from '@/types/agent.types';

export type ChatStatus =
  | 'idle'
  | 'streaming'
  | 'done'
  | 'error'
  | 'awaiting_approval'; // Plan 05-06 / D-06 sixth event

export interface ChatStreamState {
  status: ChatStatus;
  /** Current-turn trace only (D-08). Cleared on every send(). */
  liveTrace: TraceEntry[];
  finalPayload: FinalPayload | null;
  threadId: string | null;
  error: { message: string; retryable: boolean } | null;
  /** Plan 05-06 — populated when SSE emits approval_required. */
  approvalPayload: ApprovalPayload | null;
}

type Action =
  | { type: 'START' }
  | { type: 'META'; threadId: string }
  | { type: 'TRACE'; entry: TraceEntry }
  | { type: 'ANSWER'; payload: FinalPayload }
  | { type: 'ERROR'; error: { message: string; retryable: boolean } }
  | { type: 'DONE' }
  | { type: 'RESET'; threadId: string | null }
  // Plan 05-06:
  | { type: 'APPROVAL_REQUIRED'; payload: ApprovalPayload }
  | { type: 'RESUME_START' };

const INITIAL: ChatStreamState = {
  status: 'idle',
  liveTrace: [],
  finalPayload: null,
  threadId: null,
  error: null,
  approvalPayload: null,
};

function reducer(state: ChatStreamState, action: Action): ChatStreamState {
  switch (action.type) {
    case 'START':
      return {
        ...state,
        status: 'streaming',
        liveTrace: [],
        finalPayload: null,
        error: null,
        approvalPayload: null,
      };
    case 'META':
      return { ...state, threadId: action.threadId };
    case 'TRACE':
      return { ...state, liveTrace: [...state.liveTrace, action.entry] };
    case 'ANSWER':
      return { ...state, finalPayload: action.payload };
    case 'ERROR':
      return { ...state, status: 'error', error: action.error };
    case 'DONE':
      // Pitfall 2: never auto-flip 'awaiting_approval' → 'done'. The backend
      // closes the stream without a 'done' event when paused for HITL, but
      // the finally block here dispatches DONE unconditionally; this guard
      // keeps the Approve/Deny buttons live until the resume call lands.
      if (state.status === 'error' || state.status === 'awaiting_approval') {
        return state;
      }
      return { ...state, status: 'done' };
    case 'RESET':
      return { ...INITIAL, threadId: action.threadId };
    case 'APPROVAL_REQUIRED':
      return {
        ...state,
        status: 'awaiting_approval',
        approvalPayload: action.payload,
      };
    case 'RESUME_START':
      return {
        ...state,
        status: 'streaming',
        error: null,
        liveTrace: [],
        approvalPayload: null,
      };
  }
}

/**
 * Hook that owns a single in-flight chat turn. Exposes a tagged-union state
 * machine and isolates fetch / abort / localStorage side effects from the
 * pure-render UI in 04-03.
 *
 * Plan 05-06: extended with the sixth SSE event (approval_required) and an
 * `approve(threadId, decision)` callback that POSTs {thread_id, approve} to
 * resume the paused graph.
 */
export function useChatStream() {
  const [state, dispatch] = useReducer(reducer, INITIAL);
  const abortRef = useRef<AbortController | null>(null);
  // Mirror threadId in a ref so send() always reads the latest value without
  // re-creating the callback (avoids stale-closure across re-renders).
  const threadIdRef = useRef<string | null>(null);

  // Pitfall 6: read localStorage post-mount to avoid SSR hydration mismatch.
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const stored = window.localStorage.getItem(LOCAL_STORAGE_KEYS.threadId);
    if (stored) {
      threadIdRef.current = stored;
      dispatch({ type: 'META', threadId: stored });
    }
  }, []);

  // Keep ref in sync with state for read-after-meta correctness.
  useEffect(() => {
    threadIdRef.current = state.threadId;
  }, [state.threadId]);

  const send = useCallback(async (message: string, originHubId?: string) => {
    // Pitfall 7: abort any in-flight stream before starting a new one.
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    dispatch({ type: 'START' });
    let sawError = false;

    try {
      const response = await api.postChat(
        {
          message,
          thread_id: threadIdRef.current ?? undefined,
          // Phase 999.9 D-08: forward originHubId when provided.
          // Undefined = backend API boundary defaults to 'hq-lat-krabang' (Pitfall 1).
          origin_hub_id: originHubId,
        },
        controller.signal,
      );
      if (!response.ok) {
        sawError = true;
        dispatch({
          type: 'ERROR',
          error: {
            message: `HTTP ${response.status}`,
            retryable: response.status >= 500,
          },
        });
        return;
      }
      await parseSseStream(
        response,
        (ev: SSEEvent) => {
          switch (ev.type) {
            case 'meta':
              threadIdRef.current = ev.payload.thread_id;
              dispatch({ type: 'META', threadId: ev.payload.thread_id });
              if (typeof window !== 'undefined') {
                window.localStorage.setItem(
                  LOCAL_STORAGE_KEYS.threadId,
                  ev.payload.thread_id,
                );
              }
              break;
            case 'trace':
              dispatch({ type: 'TRACE', entry: ev.payload });
              break;
            case 'answer':
              dispatch({ type: 'ANSWER', payload: ev.payload });
              break;
            case 'error':
              sawError = true;
              dispatch({ type: 'ERROR', error: ev.payload });
              break;
            case 'done':
              // Handled in finally so an error before 'done' still flips state correctly.
              break;
            case 'approval_required':
              dispatch({ type: 'APPROVAL_REQUIRED', payload: ev.payload });
              break;
          }
        },
        controller.signal,
      );
    } catch (err) {
      // Aborted streams (Pitfall 7 cancel) are not errors — silently exit.
      if (err instanceof DOMException && err.name === 'AbortError') return;
      if (controller.signal.aborted) return;
      sawError = true;
      const msg = err instanceof ApiError ? err.message : String(err);
      dispatch({ type: 'ERROR', error: { message: msg, retryable: false } });
    } finally {
      if (controller.signal.aborted) {
        // Aborted by a newer send() — leave state untouched.
        if (abortRef.current === controller) abortRef.current = null;
        return;
      }
      // Reducer guards DONE so it preserves 'error' and 'awaiting_approval'
      // (Pitfall 2 — paused HITL stream keeps Approve/Deny buttons live).
      if (!sawError) dispatch({ type: 'DONE' });
      if (abortRef.current === controller) abortRef.current = null;
    }
  }, []);

  /**
   * Plan 05-06 — Resume a paused HITL graph by POSTing {thread_id, approve}.
   * Re-streams the resulting SSE events through the same reducer pipeline
   * as `send()`. On error, status flips to 'error' (Approve/Deny buttons
   * stay visible via the existing UI gate).
   */
  const approve = useCallback(
    async (threadId: string, decision: boolean) => {
      // Pitfall 7 (defensive — there should be no in-flight stream while paused).
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;

      dispatch({ type: 'RESUME_START' });
      let sawError = false;
      try {
        const response = await api.postChat(
          { thread_id: threadId, approve: decision },
          controller.signal,
        );
        if (!response.ok) {
          sawError = true;
          dispatch({
            type: 'ERROR',
            error: {
              message: `HTTP ${response.status}`,
              retryable: response.status >= 500,
            },
          });
          return;
        }
        await parseSseStream(
          response,
          (ev: SSEEvent) => {
            switch (ev.type) {
              case 'meta':
                threadIdRef.current = ev.payload.thread_id;
                dispatch({ type: 'META', threadId: ev.payload.thread_id });
                break;
              case 'trace':
                dispatch({ type: 'TRACE', entry: ev.payload });
                break;
              case 'answer':
                dispatch({ type: 'ANSWER', payload: ev.payload });
                break;
              case 'error':
                sawError = true;
                dispatch({ type: 'ERROR', error: ev.payload });
                break;
              case 'done':
                break;
              case 'approval_required':
                // Should not happen on resume, but defensive.
                dispatch({ type: 'APPROVAL_REQUIRED', payload: ev.payload });
                break;
            }
          },
          controller.signal,
        );
      } catch (err) {
        if (err instanceof DOMException && err.name === 'AbortError') return;
        if (controller.signal.aborted) return;
        sawError = true;
        const msg = err instanceof ApiError ? err.message : String(err);
        dispatch({ type: 'ERROR', error: { message: msg, retryable: false } });
      } finally {
        if (controller.signal.aborted) {
          if (abortRef.current === controller) abortRef.current = null;
          return;
        }
        if (!sawError) dispatch({ type: 'DONE' });
        if (abortRef.current === controller) abortRef.current = null;
      }
    },
    [],
  );

  const reset = useCallback(() => {
    abortRef.current?.abort();
    threadIdRef.current = null;
    if (typeof window !== 'undefined') {
      window.localStorage.removeItem(LOCAL_STORAGE_KEYS.threadId);
    }
    dispatch({ type: 'RESET', threadId: null });
  }, []);

  /**
   * Phase 7 Rule 2 / D-11 — public setter so handleResume in ChatApp can
   * propagate the resumed thread_id into chat state. Without this the
   * FeedbackButtons render gate (threadId truthy) never fires for replayed
   * messages — feedback was silently broken on every resumed conversation
   * before Phase 7.
   *
   * Resets transient turn state (liveTrace, finalPayload, error,
   * approvalPayload) so a resume cleanly drops the previous turn's UI
   * before replaying history; mirrors RESET semantics with a non-null
   * threadId.
   */
  const setThreadId = useCallback((threadId: string) => {
    threadIdRef.current = threadId;
    dispatch({ type: 'RESET', threadId });
  }, []);

  return { ...state, send, reset, approve, setThreadId };
}
