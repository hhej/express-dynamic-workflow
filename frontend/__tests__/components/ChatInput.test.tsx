import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ChatInput } from '@/components/chat/ChatInput';

describe('ChatInput', () => {
  it('renders the LOCKED placeholder copy', () => {
    render(<ChatInput onSend={() => {}} />);
    expect(
      screen.getByPlaceholderText(
        /Ask about a surcharge, e.g., 15kg Bounce from Bangkok to Nonthaburi/,
      ),
    ).toBeInTheDocument();
  });

  it('send button has aria-label "Send message" and uses bg-blue-600', () => {
    render(<ChatInput onSend={() => {}} />);
    const btn = screen.getByRole('button', { name: 'Send message' });
    expect(btn.className).toContain('bg-blue-600');
  });

  it('submitting calls onSend with trimmed text and clears the input', async () => {
    const user = userEvent.setup();
    const onSend = vi.fn();
    render(<ChatInput onSend={onSend} />);
    const ta = screen.getByPlaceholderText(/Ask about a surcharge/);
    await user.type(ta, '   hello surcharge   ');
    await user.click(screen.getByRole('button', { name: 'Send message' }));
    expect(onSend).toHaveBeenCalledWith('hello surcharge');
    expect(ta).toHaveValue('');
  });

  it('disables both controls when disabled=true', () => {
    render(<ChatInput onSend={() => {}} disabled />);
    expect(screen.getByPlaceholderText(/Ask about a surcharge/)).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Send message' })).toBeDisabled();
  });

  it('does NOT fire onSend on whitespace-only input', async () => {
    const user = userEvent.setup();
    const onSend = vi.fn();
    render(<ChatInput onSend={onSend} />);
    const ta = screen.getByPlaceholderText(/Ask about a surcharge/);
    await user.type(ta, '     ');
    const btn = screen.getByRole('button', { name: 'Send message' });
    expect(btn).toBeDisabled();
    await user.click(btn);
    expect(onSend).not.toHaveBeenCalled();
  });
});
