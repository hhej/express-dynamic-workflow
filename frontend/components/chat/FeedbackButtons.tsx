'use client';
import { useState } from 'react';
import clsx from 'clsx';
import { api } from '@/lib/api';

interface Props {
  threadId: string;
  messageId: string;
}

type Score = 'up' | 'down';

/**
 * Plan 05-06 D-16: swap localStorage stub for api.postFeedback().
 * UI is unchanged — same glyphs, same aria-pressed, same disabled-after-vote.
 * On POST failure: button stays voted, error logged to console (silent — no
 * toast). Feedback failure must NEVER block the surcharge UX.
 */
export function FeedbackButtons({ threadId, messageId }: Props) {
  const [voted, setVoted] = useState<Score | null>(null);

  async function vote(score: Score) {
    setVoted(score);
    try {
      await api.postFeedback({
        thread_id: threadId,
        message_id: messageId,
        score,
      });
    } catch (err) {
      // eslint-disable-next-line no-console
      console.error('[feedback]', err);
    }
  }

  return (
    <div className="flex gap-1 text-sm">
      <button
        type="button"
        aria-label="Helpful"
        aria-pressed={voted === 'up'}
        disabled={voted !== null}
        onClick={() => vote('up')}
        className={clsx(
          voted === 'up' ? 'opacity-100' : 'opacity-50 hover:opacity-100',
        )}
      >
        👍
      </button>
      <button
        type="button"
        aria-label="Not helpful"
        aria-pressed={voted === 'down'}
        disabled={voted !== null}
        onClick={() => vote('down')}
        className={clsx(
          voted === 'down' ? 'opacity-100' : 'opacity-50 hover:opacity-100',
        )}
      >
        👎
      </button>
    </div>
  );
}
