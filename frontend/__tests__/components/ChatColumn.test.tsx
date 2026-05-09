import { describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ChatColumn } from '@/components/chat/ChatColumn';
import { HAPPY_PAYLOAD } from '../fixtures/sse';
import type { ChatMessage } from '@/components/chat/MessageList';
import type { ApprovalPayload } from '@/types/agent.types';

const SAMPLE_MESSAGES: ChatMessage[] = [
  { role: 'user', content: 'Surcharge for 15kg Bounce, Bangkok → Nonthaburi' },
  { role: 'assistant', id: 'a1', payload: HAPPY_PAYLOAD },
];

const APPROVAL_PAYLOAD: ApprovalPayload = {
  thread_id: 't-test',
  surcharge_result: {
    surcharge_pct: 0.1,
    surcharge_amount: 65,
    total: 715,
    capped: false,
  },
  threshold: 500,
};

describe('ChatColumn (D-04 tab toggle)', () => {
  it('renders LOCKED tab labels "Chat" and "Dashboard" with Chat active by default', () => {
    render(
      <ChatColumn
        messages={[]}
        threadId={null}
        inputDisabled={false}
        onSend={() => {}}
      />,
    );
    const chatTab = screen.getByRole('button', { name: 'Chat' });
    const dashboardTab = screen.getByRole('button', { name: 'Dashboard' });
    expect(chatTab).toHaveAttribute('aria-pressed', 'true');
    expect(dashboardTab).toHaveAttribute('aria-pressed', 'false');
  });

  it('active tab uses brand-gradient + text-white, inactive uses glass-surface + readable text', () => {
    render(
      <ChatColumn
        messages={[]}
        threadId={null}
        inputDisabled={false}
        onSend={() => {}}
      />,
    );
    const active = screen.getByRole('button', { name: 'Chat' });
    expect(active.className).toContain('brand-gradient');
    expect(active.className).toContain('text-white');
    const inactive = screen.getByRole('button', { name: 'Dashboard' });
    expect(inactive.className).toContain('glass-surface');
    expect(inactive.className).toContain('text-text-primary');
  });

  it('clicking Dashboard tab reveals DashboardView heading', async () => {
    const user = userEvent.setup();
    render(
      <ChatColumn
        messages={SAMPLE_MESSAGES}
        threadId="t1"
        inputDisabled={false}
        onSend={() => {}}
      />,
    );
    await user.click(screen.getByRole('button', { name: 'Dashboard' }));
    expect(screen.getByRole('heading', { name: 'Dashboard' })).toBeInTheDocument();
  });

  it('switching tabs does NOT unmount the chat — send button persists across toggle', async () => {
    const user = userEvent.setup();
    render(
      <ChatColumn
        messages={SAMPLE_MESSAGES}
        threadId="t1"
        inputDisabled={false}
        onSend={() => {}}
      />,
    );
    // Initially Chat is visible — send button present.
    expect(
      screen.getByRole('button', { name: 'Send message' }),
    ).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Dashboard' }));
    // After switch, send button is hidden but still mounted (visibility-only via Tailwind hidden).
    expect(
      screen.getByRole('button', { name: 'Send message' }),
    ).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Chat' }));
    expect(
      screen.getByRole('button', { name: 'Send message' }),
    ).toBeInTheDocument();
  });

  it('disables ChatInput when inputDisabled=true', () => {
    render(
      <ChatColumn
        messages={[]}
        threadId={null}
        inputDisabled={true}
        onSend={() => {}}
      />,
    );
    expect(screen.getByRole('button', { name: 'Send message' })).toBeDisabled();
  });

  it('typing + sending fires onSend with the message', async () => {
    const user = userEvent.setup();
    const onSend = vi.fn();
    render(
      <ChatColumn
        messages={[]}
        threadId={null}
        inputDisabled={false}
        onSend={onSend}
      />,
    );
    await user.type(
      screen.getByPlaceholderText(/Ask about a surcharge/),
      'hello',
    );
    await user.click(screen.getByRole('button', { name: 'Send message' }));
    expect(onSend).toHaveBeenCalledWith('hello');
  });

  it('forwards awaitingApproval/onApprove/onDeny to MessageList — ApprovalCard appears (D-15.2)', () => {
    const onApprove = vi.fn();
    const onDeny = vi.fn();
    // Provide an assistant message so the "isLast" slot in MessageList exists for ApprovalCard.
    const messagesWithLastAssistant: ChatMessage[] = [
      { role: 'user', content: 'high-value query' },
      { role: 'assistant', id: 'pending-1', payload: null },
    ];
    // Render once to verify ApprovalCard appears + Approve wires through.
    const { unmount } = render(
      <ChatColumn
        messages={messagesWithLastAssistant}
        threadId="t-test"
        inputDisabled={true}
        onSend={() => {}}
        awaitingApproval={APPROVAL_PAYLOAD}
        onApprove={onApprove}
        onDeny={onDeny}
      />,
    );
    // ApprovalCard heading must be in the tree — proves the prop chain forwarded.
    expect(screen.getByText('Approval required')).toBeInTheDocument();
    // Approve button must be wired through.
    fireEvent.click(screen.getByRole('button', { name: /Approve/ }));
    expect(onApprove).toHaveBeenCalled();
    unmount();
    // Re-render to verify Deny wires through (fresh ApprovalCard waiting state).
    render(
      <ChatColumn
        messages={messagesWithLastAssistant}
        threadId="t-test"
        inputDisabled={true}
        onSend={() => {}}
        awaitingApproval={APPROVAL_PAYLOAD}
        onApprove={onApprove}
        onDeny={onDeny}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: /Deny/ }));
    expect(onDeny).toHaveBeenCalled();
  });

  it('forwards approvalErrorMessage to ApprovalCard inline error line (D-13)', () => {
    const messagesWithLastAssistant: ChatMessage[] = [
      { role: 'user', content: 'high-value query' },
      { role: 'assistant', id: 'pending-1', payload: null },
    ];
    render(
      <ChatColumn
        messages={messagesWithLastAssistant}
        threadId="t-test"
        inputDisabled={true}
        onSend={() => {}}
        awaitingApproval={APPROVAL_PAYLOAD}
        onApprove={() => {}}
        onDeny={() => {}}
        approvalErrorMessage="Could not send your decision — try again."
      />,
    );
    expect(
      screen.getByText(/Could not send your decision/),
    ).toBeInTheDocument();
  });

  it('forwards placeholder prop to ChatInput textarea (D-08)', () => {
    render(
      <ChatColumn
        messages={[]}
        threadId={null}
        inputDisabled={true}
        onSend={() => {}}
        placeholder="Awaiting your approval — use Approve / Deny above"
      />,
    );
    expect(
      screen.getByPlaceholderText(
        'Awaiting your approval — use Approve / Deny above',
      ),
    ).toBeInTheDocument();
  });
});
