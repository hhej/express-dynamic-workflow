import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MessageList, type ChatMessage } from '@/components/chat/MessageList';
import { HAPPY_PAYLOAD, CLARIFY_PAYLOAD, PARTIAL_PAYLOAD } from '../fixtures/sse';

describe('MessageList (D-12 dispatch)', () => {
  it('renders MarkdownAnswer (table) for status="ok"', () => {
    const messages: ChatMessage[] = [
      { role: 'assistant', id: 'm1', payload: HAPPY_PAYLOAD },
    ];
    render(<MessageList messages={messages} threadId="t1" />);
    expect(screen.getByRole('table')).toBeInTheDocument();
  });

  it('renders ClarifyCard for status="clarify"', () => {
    const messages: ChatMessage[] = [
      { role: 'assistant', id: 'm2', payload: CLARIFY_PAYLOAD },
    ];
    render(<MessageList messages={messages} threadId="t1" />);
    expect(
      screen.getByRole('heading', { name: /I need a bit more info/i }),
    ).toBeInTheDocument();
    expect(screen.queryByRole('table')).toBeNull();
  });

  it('renders PartialCard for status="partial"', () => {
    const messages: ChatMessage[] = [
      { role: 'assistant', id: 'm3', payload: PARTIAL_PAYLOAD },
    ];
    render(<MessageList messages={messages} threadId="t1" />);
    expect(
      screen.getByRole('heading', { name: /Limited result/i }),
    ).toBeInTheDocument();
  });

  it('renders user messages with their content', () => {
    const messages: ChatMessage[] = [
      { role: 'user', content: 'Surcharge for 15kg Bounce, Bangkok → Nonthaburi' },
    ];
    render(<MessageList messages={messages} threadId="t1" />);
    expect(screen.getByText(/Surcharge for 15kg Bounce/)).toBeInTheDocument();
  });
});
