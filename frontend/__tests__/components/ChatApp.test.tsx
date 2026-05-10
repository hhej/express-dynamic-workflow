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

/**
 * Phase 999.9 D-08 — HubPicker integration with ChatApp state lifting.
 * Tests that originHubId is correctly initialized, seeded from sessionStorage
 * post-hydration, persisted on change, forwarded to chat.send(), and
 * preserved across resume + new-conversation paths (UI-SPEC §Interaction Contracts).
 */
describe('ChatApp HubPicker integration (Phase 999.9 D-08)', () => {
  beforeEach(() => {
    window.sessionStorage.clear();
  });

  it('initializes originHubId to DEFAULT_HUB_ID on cold render', async () => {
    render(<ChatApp />);
    await waitFor(() =>
      expect(screen.getByLabelText('Origin hub')).toBeInTheDocument(),
    );
    const select = screen.getByLabelText('Origin hub') as HTMLSelectElement;
    expect(select.value).toBe('hq-lat-krabang');
  });

  it('seeds originHubId from sessionStorage post-mount when valid hub_id stored (Pitfall 6)', async () => {
    window.sessionStorage.setItem('express_origin_hub_id', 'branch-bang-na');
    render(<ChatApp />);
    await waitFor(() => {
      const select = screen.getByLabelText('Origin hub') as HTMLSelectElement;
      expect(select.value).toBe('branch-bang-na');
    });
  });

  it('falls back to DEFAULT_HUB_ID when sessionStorage holds an invalid hub_id (allowlist guard)', async () => {
    window.sessionStorage.setItem('express_origin_hub_id', 'invalid-hub-9001');
    render(<ChatApp />);
    await waitFor(() =>
      expect(screen.getByLabelText('Origin hub')).toBeInTheDocument(),
    );
    const select = screen.getByLabelText('Origin hub') as HTMLSelectElement;
    expect(select.value).toBe('hq-lat-krabang');
  });

  it('persists hub change to sessionStorage', async () => {
    const user = userEvent.setup();
    render(<ChatApp />);
    await waitFor(() =>
      expect(screen.getByLabelText('Origin hub')).toBeInTheDocument(),
    );
    await user.selectOptions(
      screen.getByLabelText('Origin hub'),
      'branch-ayutthaya',
    );
    await waitFor(() =>
      expect(window.sessionStorage.getItem('express_origin_hub_id')).toBe(
        'branch-ayutthaya',
      ),
    );
  });

  it('forwards origin_hub_id in POST /api/chat body when user sends a message', async () => {
    const user = userEvent.setup();
    let capturedBody: { message?: string; origin_hub_id?: string } | null = null;
    server.use(
      http.post('http://localhost:8000/api/chat', async ({ request }) => {
        capturedBody = (await request.json()) as typeof capturedBody;
        return sseResponse();
      }),
    );
    render(<ChatApp />);
    await waitFor(() =>
      expect(screen.getByLabelText('Origin hub')).toBeInTheDocument(),
    );
    await user.selectOptions(
      screen.getByLabelText('Origin hub'),
      'branch-bang-na',
    );
    await user.type(
      screen.getByPlaceholderText(/Ask about a surcharge/),
      'test query',
    );
    await user.click(screen.getByRole('button', { name: 'Send message' }));
    await waitFor(() => {
      expect(capturedBody).not.toBeNull();
      expect(capturedBody!.origin_hub_id).toBe('branch-bang-na');
    });
  });

  it('resuming a thread does NOT reset HubPicker (UI-SPEC: dropdown represents current selection, not resumed thread)', async () => {
    const user = userEvent.setup();
    window.sessionStorage.setItem('express_origin_hub_id', 'branch-bang-na');
    render(<ChatApp />);
    // Wait for post-hydration sessionStorage seeding.
    await waitFor(() => {
      const select = screen.getByLabelText('Origin hub') as HTMLSelectElement;
      expect(select.value).toBe('branch-bang-na');
    });
    // Click a thread in the sidebar to resume.
    const threadButton = await screen.findByRole('button', {
      name: /Resume Surcharge for 15kg Bounce/,
    });
    await user.click(threadButton);
    // Wait for replay to complete.
    await waitFor(() => {
      const userBubbles = screen
        .getAllByText(/Surcharge for 15kg Bounce/)
        .filter((el) => el.tagName.toLowerCase() === 'li');
      expect(userBubbles.length).toBeGreaterThan(0);
    });
    // HubPicker MUST still be on 'branch-bang-na' (UI-SPEC §Interaction Contracts).
    const select = screen.getByLabelText('Origin hub') as HTMLSelectElement;
    expect(select.value).toBe('branch-bang-na');
  });
});
