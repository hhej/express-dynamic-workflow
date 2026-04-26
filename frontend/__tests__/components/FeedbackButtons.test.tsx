import { describe, expect, it, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { FeedbackButtons } from '@/components/chat/FeedbackButtons';
import { LOCAL_STORAGE_KEYS } from '@/lib/constants';

beforeEach(() => {
  window.localStorage.clear();
});

describe('FeedbackButtons (UI-05 stub per D-17)', () => {
  it('renders 👍 and 👎 with the LOCKED aria-labels', () => {
    render(<FeedbackButtons threadId="t1" messageId="m1" />);
    expect(screen.getByRole('button', { name: 'Helpful' })).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'Not helpful' }),
    ).toBeInTheDocument();
  });

  it('clicking 👍 appends an entry to localStorage[feedback] as a JSON array', async () => {
    const user = userEvent.setup();
    render(<FeedbackButtons threadId="t1" messageId="m1" />);
    await user.click(screen.getByRole('button', { name: 'Helpful' }));
    const stored = JSON.parse(
      window.localStorage.getItem(LOCAL_STORAGE_KEYS.feedback) ?? '[]',
    );
    expect(stored).toHaveLength(1);
    expect(stored[0]).toMatchObject({
      thread_id: 't1',
      message_id: 'm1',
      score: 'up',
    });
  });

  it('after voting, both buttons are disabled and the voted button has aria-pressed=true', async () => {
    const user = userEvent.setup();
    render(<FeedbackButtons threadId="t1" messageId="m1" />);
    await user.click(screen.getByRole('button', { name: 'Not helpful' }));
    expect(screen.getByRole('button', { name: 'Helpful' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Not helpful' })).toBeDisabled();
    expect(
      screen.getByRole('button', { name: 'Not helpful' }),
    ).toHaveAttribute('aria-pressed', 'true');
  });

  it('NEVER calls fetch (UI-05 is wire-deferred to Phase 5)', async () => {
    const user = userEvent.setup();
    const fetchSpy = vi.spyOn(globalThis, 'fetch');
    render(<FeedbackButtons threadId="t1" messageId="m1" />);
    await user.click(screen.getByRole('button', { name: 'Helpful' }));
    expect(fetchSpy).not.toHaveBeenCalled();
    fetchSpy.mockRestore();
  });
});
