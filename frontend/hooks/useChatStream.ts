'use client';
import { useCallback, useEffect, useReducer, useRef } from 'react';
import { api, ApiError } from '@/lib/api';
import { parseSseStream } from '@/lib/sse';
import { LOCAL_STORAGE_KEYS } from '@/lib/constants';
import type { FinalPayload, SSEEvent, TraceEntry } from '@/types/agent.types';

export type ChatStatus = 'idle' | 'streaming' | 'done' | 'error';

export interface ChatStreamState {
  status: ChatStatus;
  /** Current-turn trace only (D-08). Cleared on every send(). */
  liveTrace: TraceEntry[];
  finalPayload: FinalPayload | null;
  threadId: string | null;
  error: { message: string; retryable: boolean } | null;
}

type Action =
  | { type: 'START' }
  | { type: 'META'; threadId: string }
  | { type: 'TRACE'; entry: TraceEntry }
  | { type: 'ANSWER'; payload: FinalPayload }
  | { type: 'ERROR'; error: { message: string; retryable: boolean } }
  | { type: 'DONE' }
  | { type: 'RESET'; threadId: string | null };

const INITIAL: ChatStreamState = {
  status: 'idle',
  liveTrace: [],
  finalPayload: null,
  threadId: null,
  error: null,
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
      return state.status === 'error' ? state : { ...state, status: 'done' };
    case 'RESET':
      return { ...INITIAL, threadId: action.threadId };
  }
}

/**
 * Hook that owns a single in-flight chat turn. Exposes a tagged-union state
 * machine and isolates fetch / abort / localStorage side effects from the
 * pure-render UI in 04-03.
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

  const send = useCallback(async (message: string) => {
    // Pitfall 7: abort any in-flight stream before starting a new one.
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    dispatch({ type: 'START' });
    let sawError = false;

    try {
      const response = await api.postChat(
        { message, thread_id: threadIdRef.current ?? undefined },
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
      if (!sawError) dispatch({ type: 'DONE' });
      if (abortRef.current === controller) abortRef.current = null;
    }
  }, []);

  const reset = useCallback(() => {
    abortRef.current?.abort();
    threadIdRef.current = null;
    if (typeof window !== 'undefined') {
      window.localStorage.removeItem(LOCAL_STORAGE_KEYS.threadId);
    }
    dispatch({ type: 'RESET', threadId: null });
  }, []);

  return { ...state, send, reset };
}
