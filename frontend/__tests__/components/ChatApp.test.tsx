import { describe, expect, it, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { ChatApp } from '@/components/ChatApp';
import { server } from '../mocks/server';
import { happyTurnEvents, makeSseStream } from '../fixtures/sse';

function sseResponse(events = happyTurnEvents()) {
  return new HttpResponse(makeSseStream(events), {
    headers: { 'Content-Type': 'text/event-stream' },
  });
}

beforeEach(() => {
  window.localStorage.clear();
});

describe('ChatApp (integration of all 04-03 + 04-04 components)', () => {
  it('renders the three columns: sidebar + chat column + trace panel', async () => {
    render(<ChatApp />);
    await waitFor(() => {
      expect(
        screen.getByRole('heading', { name: 'Conversations' }),
      ).toBeInTheDocument();
      expect(
        screen.getByRole('heading', { name: 'Reasoning trace' }),
      ).toBeInTheDocument();
      expect(screen.getByRole('button', { name: 'Chat' })).toBeInTheDocument();
    });
  });

  it('sending a message appends user msg + streams trace entries + appends assistant msg', async () => {
    const user = userEvent.setup();
    server.use(http.post('http://localhost:8000/api/chat', () => sseResponse()));
    render(<ChatApp />);
    await waitFor(() => screen.getByRole('button', { name: 'Send message' }));
    await user.type(
      screen.getByPlaceholderText(/Ask about a surcharge/),
      'Surcharge for 15kg Bounce, Bangkok → Nonthaburi',
    );
    await user.click(screen.getByRole('button', { name: 'Send message' }));
    // User message visible (user-message bubble in MessageList)
    await waitFor(() =>
      expect(
        screen.getByText(
          /Surcharge for 15kg Bounce, Bangkok → Nonthaburi/,
          { selector: 'li' },
        ),
      ).toBeInTheDocument(),
    );
    // After stream completes, breakdown table visible
    await waitFor(
      () => expect(screen.getByRole('table')).toBeInTheDocument(),
      { timeout: 4000 },
    );
    // Trace panel populated with at least 5 expandable trace step buttons.
    const traceSteps = screen
      .getAllByRole('button')
      .filter((b) => b.getAttribute('aria-expanded') !== null);
    expect(traceSteps.length).toBeGreaterThanOrEqual(5);
  });

  it('after stream done, ChatInput is re-enabled', async () => {
    const user = userEvent.setup();
    server.use(http.post('http://localhost:8000/api/chat', () => sseResponse()));
    render(<ChatApp />);
    await waitFor(() => screen.getByRole('button', { name: 'Send message' }));
    await user.type(
      screen.getByPlaceholderText(/Ask about a surcharge/),
      'hi',
    );
    await user.click(screen.getByRole('button', { name: 'Send message' }));
    await waitFor(
      () => expect(screen.getByRole('table')).toBeInTheDocument(),
      { timeout: 4000 },
    );
    // Send button re-enabled (after typing new input)
    await user.type(
      screen.getByPlaceholderText(/Ask about a surcharge/),
      'next',
    );
    expect(screen.getByRole('button', { name: 'Send message' })).not.toBeDisabled();
  });

  it('"+ New conversation" clears the chat surface', async () => {
    const user = userEvent.setup();
    server.use(http.post('http://localhost:8000/api/chat', () => sseResponse()));
    render(<ChatApp />);
    await waitFor(() => screen.getByRole('button', { name: 'Send message' }));
    await user.type(
      screen.getByPlaceholderText(/Ask about a surcharge/),
      'hi',
    );
    await user.click(screen.getByRole('button', { name: 'Send message' }));
    await waitFor(
      () => expect(screen.getByRole('table')).toBeInTheDocument(),
      { timeout: 4000 },
    );
    // Now click "+ New conversation"
    await user.click(screen.getByRole('button', { name: '+ New conversation' }));
    // Table should disappear
    await waitFor(() => expect(screen.queryByRole('table')).toBeNull());
  });

  it('resuming a thread from sidebar replays prior messages into the chat surface', async () => {
    const user = userEvent.setup();
    render(<ChatApp />);
    // Wait for sidebar to populate with thread previews from default MSW handler
    const threadButton = await screen.findByRole('button', {
      name: /Resume Surcharge for 15kg Bounce/,
    });
    await user.click(threadButton);
    // Chat surface shows prior user message from default getConversation handler
    await waitFor(() => {
      const userBubbles = screen
        .getAllByText(/Surcharge for 15kg Bounce/)
        .filter((el) => el.tagName.toLowerCase() === 'li');
      expect(userBubbles.length).toBeGreaterThan(0);
    });
  });
});
