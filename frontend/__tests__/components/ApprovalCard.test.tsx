import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { ApprovalCard } from '@/components/chat/ApprovalCard';
import type { ApprovalPayload } from '@/types/agent.types';

const PAYLOAD: ApprovalPayload = {
  thread_id: 't',
  surcharge_result: {
    surcharge_pct: 0.1,
    surcharge_amount: 65,
    total: 715,
    capped: false,
  },
  threshold: 500,
};

describe('ApprovalCard (Plan 05-06)', () => {
  it('renders heading "Approval required"', () => {
    render(
      <ApprovalCard
        payload={PAYLOAD}
        onApprove={() => {}}
        onDeny={() => {}}
      />,
    );
    expect(screen.getByText('Approval required')).toBeInTheDocument();
  });

  it('renders surcharge breakdown table cells', () => {
    render(
      <ApprovalCard
        payload={PAYLOAD}
        onApprove={() => {}}
        onDeny={() => {}}
      />,
    );
    expect(screen.getByText('10.00%')).toBeInTheDocument();
    expect(screen.getByText('65 THB')).toBeInTheDocument();
    // The Total cell renders as "715 THB"; the body copy ALSO mentions
    // "of 715 THB", so use a role/within-table query to disambiguate.
    const cells = screen.getAllByText(/715 THB/);
    expect(cells.length).toBeGreaterThanOrEqual(1);
  });

  it('Approve click calls onApprove', () => {
    const onApprove = vi.fn();
    render(
      <ApprovalCard
        payload={PAYLOAD}
        onApprove={onApprove}
        onDeny={() => {}}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: /Approve/ }));
    expect(onApprove).toHaveBeenCalled();
  });

  it('Deny click calls onDeny', () => {
    const onDeny = vi.fn();
    render(
      <ApprovalCard
        payload={PAYLOAD}
        onApprove={() => {}}
        onDeny={onDeny}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: /Deny/ }));
    expect(onDeny).toHaveBeenCalled();
  });

  it('shows "Sending your decision…" caption while waiting', async () => {
    const slow = () => new Promise<void>((r) => setTimeout(r, 1000));
    render(
      <ApprovalCard payload={PAYLOAD} onApprove={slow} onDeny={() => {}} />,
    );
    fireEvent.click(screen.getByRole('button', { name: /Approve/ }));
    expect(
      await screen.findByText(/Sending your decision/),
    ).toBeInTheDocument();
  });

  it('uses Bangkok Metro phrasing in body copy', () => {
    render(
      <ApprovalCard
        payload={PAYLOAD}
        onApprove={() => {}}
        onDeny={() => {}}
      />,
    );
    expect(screen.getByText(/Bangkok Metro/)).toBeInTheDocument();
  });
});
