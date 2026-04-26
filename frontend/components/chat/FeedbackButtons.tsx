'use client';
import { useState } from 'react';
import clsx from 'clsx';
import { LOCAL_STORAGE_KEYS } from '@/lib/constants';

interface Props {
  threadId: string;
  messageId: string;
}

type Score = 'up' | 'down';

export function FeedbackButtons({ threadId, messageId }: Props) {
  const [voted, setVoted] = useState<Score | null>(null);

  function vote(score: Score) {
    setVoted(score);
    const payload = {
      thread_id: threadId,
      message_id: messageId,
      score,
      ts: new Date().toISOString(),
    };
    // D-17: local-only stub. Phase 5 swaps to api.postFeedback(payload).
    console.log('[feedback]', payload);
    try {
      const stored = JSON.parse(
        window.localStorage.getItem(LOCAL_STORAGE_KEYS.feedback) ?? '[]',
      );
      stored.push(payload);
      window.localStorage.setItem(
        LOCAL_STORAGE_KEYS.feedback,
        JSON.stringify(stored),
      );
    } catch {
      /* localStorage may be full; non-fatal */
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
