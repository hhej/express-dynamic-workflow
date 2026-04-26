import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { PartialCard } from '@/components/chat/PartialCard';
import { PARTIAL_PAYLOAD, HAPPY_PAYLOAD } from '../fixtures/sse';

describe('PartialCard (D-12)', () => {
  it('renders the locked heading and the payload markdown body', () => {
    render(<PartialCard payload={PARTIAL_PAYLOAD} />);
    expect(
      screen.getByRole('heading', { name: /Limited result/i }),
    ).toBeInTheDocument();
    expect(screen.getByText(/Limited result — fuel data fetched/i)).toBeInTheDocument();
  });

  it('uses the locked orange-50 / orange-200 classes', () => {
    const { container } = render(<PartialCard payload={PARTIAL_PAYLOAD} />);
    const card = container.firstElementChild as HTMLElement;
    expect(card.className).toContain('bg-orange-50');
    expect(card.className).toContain('border-orange-200');
  });

  it('renders the breakdown table when surcharge_result is non-null', () => {
    const partialWithResult = { ...HAPPY_PAYLOAD, status: 'partial' as const };
    render(<PartialCard payload={partialWithResult} />);
    expect(screen.getByRole('table')).toBeInTheDocument();
  });

  it('omits the breakdown table when surcharge_result is null', () => {
    render(<PartialCard payload={PARTIAL_PAYLOAD} />);
    expect(screen.queryByRole('table')).toBeNull();
  });
});
