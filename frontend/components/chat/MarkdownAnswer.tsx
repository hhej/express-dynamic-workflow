'use client';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { CapCallout } from '@/components/shared/CapCallout';
import { SearchContextLine } from '@/components/chat/SearchContextLine';
import type { FinalPayload } from '@/types/agent.types';

/** Match the leading capped-callout blockquote line emitted by backend response_node. */
const CAP_LINE_RE = /^>\s*⚠\s*Cap\/floor applied\s*—\s*review recommended\s*\n\n?/;

/**
 * Match the leading "Market context:" blockquote line emitted by backend
 * response_node (Plan 05-04 D-11). The typed SearchContextLine component
 * renders the styled version above the prose; strip the markdown line so
 * we don't render the same caption twice.
 */
const MARKET_CONTEXT_LINE_RE = /^>\s*\*\*Market context:\*\*[^\n]*\n\n?/;

export function MarkdownAnswer({ payload }: { payload: FinalPayload }) {
  const cleanCapped = payload.capped
    ? payload.markdown.replace(CAP_LINE_RE, '')
    : payload.markdown;

  const sc = payload.search_context;
  const hasMarketContext = !!(sc && (sc.summary ?? '').trim().length > 0);
  const stripped = hasMarketContext
    ? cleanCapped.replace(MARKET_CONTEXT_LINE_RE, '')
    : cleanCapped;

  return (
    <div className="space-y-3">
      {payload.capped && <CapCallout />}
      {hasMarketContext && sc && <SearchContextLine context={sc} />}
      <div className="prose prose-sm max-w-none">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            table: (props) => (
              <table className="border-collapse" {...props} />
            ),
            th: (props) => (
              <th className="border bg-gray-50 px-2 py-1 text-left" {...props} />
            ),
            td: (props) => <td className="border px-2 py-1" {...props} />,
          }}
        >
          {stripped}
        </ReactMarkdown>
      </div>
    </div>
  );
}
