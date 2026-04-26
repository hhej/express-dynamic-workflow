import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ClarifyCard } from '@/components/chat/ClarifyCard';
import { CLARIFY_PAYLOAD } from '../fixtures/sse';

describe('ClarifyCard (D-12)', () => {
  it('renders the locked heading and the payload markdown body', () => {
    render(<ClarifyCard payload={CLARIFY_PAYLOAD} />);
    expect(
      screen.getByRole('heading', { name: /I need a bit more info/i }),
    ).toBeInTheDocument();
    expect(screen.getByText(/weight, origin, and destination/i)).toBeInTheDocument();
  });

  it('uses the locked blue-50 / blue-200 classes', () => {
    const { container } = render(<ClarifyCard payload={CLARIFY_PAYLOAD} />);
    const card = container.firstElementChild as HTMLElement;
    expect(card.className).toContain('bg-blue-50');
    expect(card.className).toContain('border-blue-200');
  });

  it('does NOT render a breakdown table', () => {
    render(<ClarifyCard payload={CLARIFY_PAYLOAD} />);
    expect(screen.queryByRole('table')).toBeNull();
  });
});
