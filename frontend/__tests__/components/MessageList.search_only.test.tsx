import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MessageList, type ChatMessage } from '@/components/chat/MessageList';

/**
 * Phase 8 D-15 — drift-prevention test for the 'search_only' rendering wire.
 *
 * Catches future regression that loses the MessageList → MarkdownAnswer →
 * SearchContextLine path for status='search_only' payloads. The audit's
 * lesson is that every layer passed its own unit tests but the dispatch
 * boundary was the actual break (Issue 6).
 */
describe("MessageList — status='search_only' (Phase 8 D-15)", () => {
  it('renders SearchContextLine, sources details, and omits surcharge table', () => {
    const messages: ChatMessage[] = [
      {
        role: 'assistant',
        id: 'thread-news-0',
        payload: {
          message_id: 'thread-news-0',
          markdown:
            "> **Market context:** Diesel up 3% on supply concerns\n\nHere's the latest market context.\n\n*Reasoning trace available below.*",
          surcharge_result: null,
          capped: false,
          status: 'search_only',
          search_context: {
            query: 'diesel news',
            summary: 'Diesel up 3% on supply concerns',
            sources: [
              {
                title: 'Reuters: Thailand diesel rises',
                url: 'https://reuters.example/x',
                snippet: '...',
                published_at: '2026-05-04',
              },
            ],
            fetched_at: '2026-05-04T10:00:00Z',
          },
        },
      },
    ];
    render(<MessageList messages={messages} threadId="thread-news" />);

    // (a) SearchContextLine's typed "Market context:" caption is in the document.
    expect(screen.getByText('Market context:')).toBeInTheDocument();
    // (b) The collapsible Sources <details> toggle renders.
    expect(screen.getByText('Sources: 1')).toBeInTheDocument();
    // (c) Source link has the safety attributes.
    const link = screen.getByRole('link', { name: /Reuters/ });
    expect(link).toHaveAttribute('target', '_blank');
    expect(link).toHaveAttribute('rel', 'noopener noreferrer');
    // (d) No surcharge breakdown table renders (surcharge_result=null on search-only).
    expect(screen.queryByRole('table')).toBeNull();
  });
});
