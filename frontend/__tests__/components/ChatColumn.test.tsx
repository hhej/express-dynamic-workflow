import { describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ChatColumn } from '@/components/chat/ChatColumn';
import { HAPPY_PAYLOAD } from '../fixtures/sse';
import hubsFixture from '../fixtures/hubs.json';
import type { ChatMessage } from '@/components/chat/MessageList';
import type { ApprovalPayload, Hub } from '@/types/agent.types';

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

// Phase 999.9 D-08: hub list passed to ChatColumn.HubPicker via prop chain.
const HUBS: Hub[] = Object.entries(hubsFixture).map(([hub_id, data]) => ({
  hub_id,
  ...(data as Omit<Hub, 'hub_id'>),
}));

/**
 * Phase 999.9 — default props for the new HubPicker prop chain. Pre-existing
 * tests use these as a base + override what they exercise.
 */
const HUB_PROPS = {
  hubs: HUBS,
  originHubId: 'hq-lat-krabang',
  onHubChange: () => {},
};

describe('ChatColumn (D-04 tab toggle)', () => {
  it('renders LOCKED tab labels "Chat" and "Dashboard" with Chat active by default', () => {
    render(
      <ChatColumn
        messages={[]}
        threadId={null}
        inputDisabled={false}
        onSend={() => {}}
        {...HUB_PROPS}
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
        {...HUB_PROPS}
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
        {...HUB_PROPS}
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
        {...HUB_PROPS}
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
        {...HUB_PROPS}
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
        {...HUB_PROPS}
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
        {...HUB_PROPS}
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
        {...HUB_PROPS}
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
        {...HUB_PROPS}
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
        {...HUB_PROPS}
      />,
    );
    expect(
      screen.getByPlaceholderText(
        'Awaiting your approval — use Approve / Deny above',
      ),
    ).toBeInTheDocument();
  });
});

describe('ChatColumn HubPicker integration (Phase 999.9)', () => {
  it('renders the HubPicker dropdown with the locked aria-label', () => {
    render(
      <ChatColumn
        messages={[]}
        threadId={null}
        inputDisabled={false}
        onSend={() => {}}
        {...HUB_PROPS}
      />,
    );
    expect(screen.getByLabelText('Origin hub')).toBeInTheDocument();
  });

  it('forwards inputDisabled to the HubPicker (single source of truth with ChatInput)', () => {
    render(
      <ChatColumn
        messages={[]}
        threadId={null}
        inputDisabled={true}
        onSend={() => {}}
        {...HUB_PROPS}
      />,
    );
    // Both HubPicker and ChatInput's send button must be disabled.
    expect(screen.getByLabelText('Origin hub')).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Send message' })).toBeDisabled();
  });

  it('calls onHubChange with the chosen hub_id when user picks a different hub', async () => {
    const user = userEvent.setup();
    const onHubChange = vi.fn();
    render(
      <ChatColumn
        messages={[]}
        threadId={null}
        inputDisabled={false}
        onSend={() => {}}
        hubs={HUBS}
        originHubId="hq-lat-krabang"
        onHubChange={onHubChange}
      />,
    );
    await user.selectOptions(screen.getByLabelText('Origin hub'), 'branch-bang-na');
    expect(onHubChange).toHaveBeenCalledWith('branch-bang-na');
  });

  it('renders HubPicker BEFORE the ChatInput textarea in document order (UI-SPEC §Spacing Scale)', () => {
    const { container } = render(
      <ChatColumn
        messages={[]}
        threadId={null}
        inputDisabled={false}
        onSend={() => {}}
        {...HUB_PROPS}
      />,
    );
    const picker = container.querySelector('select#hub-picker');
    const textarea = container.querySelector('textarea');
    expect(picker).not.toBeNull();
    expect(textarea).not.toBeNull();
    // DOCUMENT_POSITION_FOLLOWING (0x04) — picker comes BEFORE textarea.
    // eslint-disable-next-line no-bitwise
    expect(picker!.compareDocumentPosition(textarea!) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });
});
