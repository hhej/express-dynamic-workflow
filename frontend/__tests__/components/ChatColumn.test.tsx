import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ChatColumn } from '@/components/chat/ChatColumn';
import { HAPPY_PAYLOAD } from '../fixtures/sse';
import type { ChatMessage } from '@/components/chat/MessageList';

const SAMPLE_MESSAGES: ChatMessage[] = [
  { role: 'user', content: 'Surcharge for 15kg Bounce, Bangkok → Nonthaburi' },
  { role: 'assistant', id: 'a1', payload: HAPPY_PAYLOAD },
];

describe('ChatColumn (D-04 tab toggle)', () => {
  it('renders LOCKED tab labels "Chat" and "Dashboard" with Chat active by default', () => {
    render(
      <ChatColumn
        messages={[]}
        threadId={null}
        isStreaming={false}
        onSend={() => {}}
      />,
    );
    const chatTab = screen.getByRole('button', { name: 'Chat' });
    const dashboardTab = screen.getByRole('button', { name: 'Dashboard' });
    expect(chatTab).toHaveAttribute('aria-pressed', 'true');
    expect(dashboardTab).toHaveAttribute('aria-pressed', 'false');
  });

  it('active tab uses LOCKED bg-blue-600 + text-white classes', () => {
    render(
      <ChatColumn
        messages={[]}
        threadId={null}
        isStreaming={false}
        onSend={() => {}}
      />,
    );
    const active = screen.getByRole('button', { name: 'Chat' });
    expect(active.className).toContain('bg-blue-600');
    expect(active.className).toContain('text-white');
    const inactive = screen.getByRole('button', { name: 'Dashboard' });
    expect(inactive.className).toContain('bg-white');
    expect(inactive.className).toContain('text-gray-700');
  });

  it('clicking Dashboard tab reveals DashboardView heading', async () => {
    const user = userEvent.setup();
    render(
      <ChatColumn
        messages={SAMPLE_MESSAGES}
        threadId="t1"
        isStreaming={false}
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
        isStreaming={false}
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

  it('disables ChatInput when isStreaming=true', () => {
    render(
      <ChatColumn
        messages={[]}
        threadId={null}
        isStreaming={true}
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
        isStreaming={false}
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
});
