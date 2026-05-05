'use client';
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import { api } from '@/lib/api';
import { LOCAL_STORAGE_KEYS } from '@/lib/constants';
import type { ConversationDetail, ConversationSummary } from '@/types/api.types';

/**
 * Phase 8 D-01 / D-02 — single React Context instance shared by ChatApp,
 * ConversationSidebar, and SurchargeHistoryChart. The provider owns the
 * useState/useEffect/useCallback block; consumers read via useContext.
 *
 * Closes audit Issue 4: when ChatApp.tsx fires `void conversations.refresh()`
 * on `done`, all three consumers re-render with the fresh items list.
 */

interface ConversationsContextValue {
  items: ConversationSummary[];
  loading: boolean;
  error: Error | null;
  refresh: () => Promise<void>;
  /** D-14 (Phase 4): load history + persist thread_id so the next chat continues it (D-20). */
  resume: (threadId: string) => Promise<ConversationDetail>;
}

// Sentinel `null` — wrapper hook detects "called outside provider" and throws.
const ConversationsContext = createContext<ConversationsContextValue | null>(null);

export function ConversationsProvider({ children }: { children: ReactNode }) {
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

  const resume = useCallback(async (threadId: string): Promise<ConversationDetail> => {
    const detail = await api.getConversation(threadId);
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(LOCAL_STORAGE_KEYS.threadId, threadId);
    }
    return detail;
  }, []);

  // Pitfall 3: stabilize value identity so consumer effects keyed on
  // `conversations.refresh` don't refire on every items/loading update.
  const value = useMemo<ConversationsContextValue>(
    () => ({ items, loading, error, refresh, resume }),
    [items, loading, error, refresh, resume],
  );

  return (
    <ConversationsContext.Provider value={value}>{children}</ConversationsContext.Provider>
  );
}

/**
 * Read the shared conversations state. Throws when called outside
 * <ConversationsProvider>. Wrap your tree in ChatApp.tsx.
 */
export function useConversations(): ConversationsContextValue {
  const ctx = useContext(ConversationsContext);
  if (ctx === null) {
    throw new Error(
      'useConversations() must be called inside <ConversationsProvider>. ' +
        'Wrap your tree with the provider in ChatApp.tsx.',
    );
  }
  return ctx;
}
