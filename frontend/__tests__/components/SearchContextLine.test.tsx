import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { SearchContextLine } from '@/components/chat/SearchContextLine';

describe('SearchContextLine (Plan 05-06)', () => {
  it('renders "Market context:" prefix and summary', () => {
    render(
      <SearchContextLine
        context={{
          query: 'q',
          summary: 'Diesel held steady.',
          sources: [],
          fetched_at: 'z',
        }}
      />,
    );
    expect(screen.getByText('Market context:')).toBeInTheDocument();
    expect(screen.getByText(/Diesel held steady/)).toBeInTheDocument();
  });

  it('returns null when summary empty', () => {
    const { container } = render(
      <SearchContextLine
        context={{ query: 'q', summary: '', sources: [], fetched_at: 'z' }}
      />,
    );
    expect(container.firstChild).toBeNull();
  });

  it('returns null when summary is whitespace-only', () => {
    const { container } = render(
      <SearchContextLine
        context={{ query: 'q', summary: '   ', sources: [], fetched_at: 'z' }}
      />,
    );
    expect(container.firstChild).toBeNull();
  });

  it('renders "Sources: N" when sources non-empty', () => {
    render(
      <SearchContextLine
        context={{
          query: 'q',
          summary: 'ok',
          sources: [
            {
              title: 'A',
              url: 'https://a',
              snippet: 's',
              published_at: '2026-05-01',
            },
          ],
          fetched_at: 'z',
        }}
      />,
    );
    expect(screen.getByText('Sources: 1')).toBeInTheDocument();
  });

  it('omits sources line when sources empty', () => {
    render(
      <SearchContextLine
        context={{ query: 'q', summary: 'ok', sources: [], fetched_at: 'z' }}
      />,
    );
    expect(screen.queryByText(/Sources:/)).toBeNull();
  });

  it('source links have target=_blank and rel=noopener noreferrer', () => {
    render(
      <SearchContextLine
        context={{
          query: 'q',
          summary: 'ok',
          sources: [
            { title: 'A', url: 'https://a', snippet: 's', published_at: null },
          ],
          fetched_at: 'z',
        }}
      />,
    );
    const link = screen.getByRole('link', { name: 'A' });
    expect(link).toHaveAttribute('target', '_blank');
    expect(link).toHaveAttribute('rel', 'noopener noreferrer');
  });
});
