import { describe, expect, it } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import { MarkdownAnswer } from '@/components/chat/MarkdownAnswer';
import { HAPPY_PAYLOAD, CAPPED_PAYLOAD } from '../fixtures/sse';

describe('MarkdownAnswer (UI-03 + D-11)', () => {
  it('renders the 4-row breakdown table from HAPPY_PAYLOAD markdown', () => {
    render(<MarkdownAnswer payload={HAPPY_PAYLOAD} />);
    const table = screen.getByRole('table');
    expect(table).toBeInTheDocument();
    const dataRows = within(table).getAllByRole('row').slice(1); // skip header row
    expect(dataRows).toHaveLength(4);
  });

  it('does NOT render CapCallout when capped=false', () => {
    render(<MarkdownAnswer payload={HAPPY_PAYLOAD} />);
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('renders CapCallout AND strips the leading "> ⚠ ..." line when capped=true', () => {
    const { container } = render(<MarkdownAnswer payload={CAPPED_PAYLOAD} />);
    const alert = screen.getByRole('alert');
    expect(alert).toHaveTextContent('Cap/floor applied — review recommended');
    // The "> ..." line should NOT be rendered as a <blockquote>.
    expect(container.querySelector('blockquote')).toBeNull();
  });

  it('renders CapCallout BEFORE the breakdown table in DOM order', () => {
    render(<MarkdownAnswer payload={CAPPED_PAYLOAD} />);
    const alert = screen.getByRole('alert');
    const table = screen.getByRole('table');
    const order = alert.compareDocumentPosition(table);
    // DOCUMENT_POSITION_FOLLOWING = 4 (table follows alert)
    expect(order & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });
});
