'use client';
import type { SearchContext } from '@/types/agent.types';

/**
 * Plan 05-04 D-11: Renders "Market context: <summary>" caption above the
 * prose answer when search_agent populated state.search_context. Optional
 * sources details collapsed by default; sources line omitted when
 * sources.length === 0. Returns null when summary is empty/whitespace-only.
 *
 * UI-SPEC contract: gray-50 bg, blue-200 left rule, italic 12px gray-700 prose
 * with semibold "Market context:" prefix; source links open in a new tab with
 * rel=noopener noreferrer.
 */
export function SearchContextLine({ context }: { context: SearchContext }) {
  const summary = (context.summary ?? '').trim();
  if (!summary) return null;
  const hasSources = context.sources.length > 0;
  return (
    <div className="border-l-2 border-blue-200 bg-gray-50 p-2">
      <p className="text-xs leading-normal text-gray-700">
        <span className="font-semibold">Market context:</span>{' '}
        <span className="italic">{summary}</span>
      </p>
      {hasSources && (
        <details className="mt-1">
          <summary className="cursor-pointer text-xs text-gray-500">
            Sources: {context.sources.length}
          </summary>
          <ul className="mt-1 space-y-1 pl-4 text-xs text-gray-500">
            {context.sources.map((s, i) => (
              <li key={`${s.url}-${i}`}>
                <a
                  href={s.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="underline"
                >
                  {s.title || s.url}
                </a>
                {s.published_at && <span> — {s.published_at}</span>}
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}
