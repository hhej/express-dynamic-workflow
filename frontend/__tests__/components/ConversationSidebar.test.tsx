import { describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { ConversationSidebar } from '@/components/sidebar/ConversationSidebar';
import { server } from '../mocks/server';

describe('ConversationSidebar (UI-06 / D-02 / D-14)', () => {
  it('renders the LOCKED heading and "+ New conversation" button', async () => {
    render(
      <ConversationSidebar
        activeThreadId={null}
        onResume={() => {}}
        onNewConversation={() => {}}
      />,
    );
    expect(
      screen.getByRole('heading', { name: 'Conversations' }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: '+ New conversation' }),
    ).toBeInTheDocument();
  });

  it('lists threads from useConversations (MSW SAMPLE_CONVERSATIONS)', async () => {
    render(
      <ConversationSidebar
        activeThreadId={null}
        onResume={() => {}}
        onNewConversation={() => {}}
      />,
    );
    await waitFor(() => {
      expect(
        screen.getByText(/Surcharge for 15kg Bounce/),
      ).toBeInTheDocument();
      expect(screen.getByText(/What about Retail Fast?/)).toBeInTheDocument();
    });
  });

  it('renders LOCKED empty state when no threads', async () => {
    server.use(
      http.get('http://localhost:8000/api/conversations', () =>
        HttpResponse.json([]),
      ),
    );
    render(
      <ConversationSidebar
        activeThreadId={null}
        onResume={() => {}}
        onNewConversation={() => {}}
      />,
    );
    await waitFor(() => {
      expect(
        screen.getByText('No conversations yet. Send a message to start.'),
      ).toBeInTheDocument();
    });
  });

  it('clicking a thread calls onResume(threadId)', async () => {
    const user = userEvent.setup();
    const onResume = vi.fn();
    render(
      <ConversationSidebar
        activeThreadId={null}
        onResume={onResume}
        onNewConversation={() => {}}
      />,
    );
    await waitFor(() => screen.getByText(/Surcharge for 15kg Bounce/));
    await user.click(screen.getByText(/Surcharge for 15kg Bounce/));
    expect(onResume).toHaveBeenCalledWith('thread-1');
  });

  it('the active thread has the bg-blue-600 / text-white accent classes', async () => {
    render(
      <ConversationSidebar
        activeThreadId="thread-1"
        onResume={() => {}}
        onNewConversation={() => {}}
      />,
    );
    await waitFor(() => screen.getByText(/Surcharge for 15kg Bounce/));
    const activeBtn = screen
      .getByText(/Surcharge for 15kg Bounce/)
      .closest('button');
    expect(activeBtn?.className).toContain('bg-blue-600');
    expect(activeBtn?.className).toContain('text-white');
  });

  it('"+ New conversation" click calls onNewConversation', async () => {
    const user = userEvent.setup();
    const onNew = vi.fn();
    render(
      <ConversationSidebar
        activeThreadId={null}
        onResume={() => {}}
        onNewConversation={onNew}
      />,
    );
    await user.click(screen.getByRole('button', { name: '+ New conversation' }));
    expect(onNew).toHaveBeenCalled();
  });
});
