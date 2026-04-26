import { describe, expect, it, beforeEach } from 'vitest';
import { act, renderHook, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { useConversations } from '@/hooks/useConversations';
import { server } from '../mocks/server';
import { LOCAL_STORAGE_KEYS } from '@/lib/constants';
import type { ConversationDetail } from '@/types/api.types';

beforeEach(() => {
  window.localStorage.clear();
});

describe('useConversations', () => {
  it('loads SAMPLE_CONVERSATIONS on mount', async () => {
    const { result } = renderHook(() => useConversations());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.items.length).toBeGreaterThan(0);
    expect(result.current.items[0]).toHaveProperty('thread_id');
  });

  it('refresh() re-fetches when underlying handler changes', async () => {
    const { result } = renderHook(() => useConversations());
    await waitFor(() => expect(result.current.loading).toBe(false));
    const initialLen = result.current.items.length;
    server.use(
      http.get('http://localhost:8000/api/conversations', () => HttpResponse.json([])),
    );
    await act(async () => {
      await result.current.refresh();
    });
    expect(result.current.items.length).toBe(0);
    expect(initialLen).toBeGreaterThan(0);
  });

  it('resume() persists thread_id to localStorage and returns detail', async () => {
    const { result } = renderHook(() => useConversations());
    await waitFor(() => expect(result.current.loading).toBe(false));
    let detail: ConversationDetail | undefined;
    await act(async () => {
      detail = await result.current.resume('thread-1');
    });
    expect(window.localStorage.getItem(LOCAL_STORAGE_KEYS.threadId)).toBe('thread-1');
    expect(detail?.thread_id).toBe('thread-1');
  });
});
