'use client';
import { useCallback, useEffect, useState } from 'react';
import { api } from '@/lib/api';
import { LOCAL_STORAGE_KEYS } from '@/lib/constants';
import type { ConversationDetail, ConversationSummary } from '@/types/api.types';

/**
 * Hook for the conversation history sidebar. Owns fetch + refresh and the
 * D-14 resume flow which persists thread_id to localStorage so the next
 * chat turn continues the resumed thread (D-20).
 */
export function useConversations() {
  const [items, setItems] = useState<ConversationSummary[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<Error | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const next = await api.listConversations(50);
      setItems(next);
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  /** D-14: load history + persist thread_id so the next chat continues it (D-20). */
  const resume = useCallback(async (threadId: string): Promise<ConversationDetail> => {
    const detail = await api.getConversation(threadId);
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(LOCAL_STORAGE_KEYS.threadId, threadId);
    }
    return detail;
  }, []);

  return { items, loading, error, refresh, resume };
}
