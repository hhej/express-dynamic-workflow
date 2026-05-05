import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { FeedbackButtons } from '@/components/chat/FeedbackButtons';
import * as apiMod from '@/lib/api';

/**
 * Plan 05-06 D-16: localStorage stub swapped for api.postFeedback().
 * UI is intentionally unchanged from Phase 4 (same glyphs, same aria-pressed,
 * same disabled-after-vote) so the visual contract from D-17 still holds.
 */
describe('FeedbackButtons (D-16 — Phase 5 wire)', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders 👍 and 👎 with the LOCKED aria-labels', () => {
    render(<FeedbackButtons threadId="t1" messageId="m1" />);
    expect(screen.getByRole('button', { name: 'Helpful' })).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'Not helpful' }),
    ).toBeInTheDocument();
  });

  it('calls api.postFeedback with score=up on thumbs-up click', async () => {
    const spy = vi
      .spyOn(apiMod.api, 'postFeedback')
      .mockResolvedValue({ status: 'ok', delivered: true });
    render(<FeedbackButtons threadId="abc" messageId="abc-0" />);
    fireEvent.click(screen.getByRole('button', { name: 'Helpful' }));
    await waitFor(() => {
      expect(spy).toHaveBeenCalledWith({
        thread_id: 'abc',
        message_id: 'abc-0',
        score: 'up',
      });
    });
  });

  it('calls api.postFeedback with score=down on thumbs-down click', async () => {
    const spy = vi
      .spyOn(apiMod.api, 'postFeedback')
      .mockResolvedValue({ status: 'ok', delivered: true });
    render(<FeedbackButtons threadId="abc" messageId="abc-0" />);
    fireEvent.click(screen.getByRole('button', { name: 'Not helpful' }));
    await waitFor(() => {
      expect(spy).toHaveBeenCalledWith({
        thread_id: 'abc',
        message_id: 'abc-0',
        score: 'down',
      });
    });
  });

  it('after voting, both buttons are disabled and the voted button has aria-pressed=true', async () => {
    vi.spyOn(apiMod.api, 'postFeedback').mockResolvedValue({
      status: 'ok',
      delivered: true,
    });
    render(<FeedbackButtons threadId="t1" messageId="m1" />);
    fireEvent.click(screen.getByRole('button', { name: 'Not helpful' }));
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Helpful' })).toBeDisabled();
    });
    expect(screen.getByRole('button', { name: 'Not helpful' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Not helpful' })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
  });

  it('failed POST stays silent (no throw to UI; button stays voted)', async () => {
    vi.spyOn(apiMod.api, 'postFeedback').mockRejectedValue(new Error('boom'));
    const errSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    render(<FeedbackButtons threadId="abc" messageId="abc-0" />);
    fireEvent.click(screen.getByRole('button', { name: 'Helpful' }));
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Helpful' })).toHaveAttribute(
        'aria-pressed',
        'true',
      );
    });
    expect(errSpy).toHaveBeenCalled();
  });
});
