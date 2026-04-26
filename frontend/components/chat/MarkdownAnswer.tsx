'use client';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { CapCallout } from '@/components/shared/CapCallout';
import type { FinalPayload } from '@/types/agent.types';

/** Match the leading capped-callout blockquote line emitted by backend response_node. */
const CAP_LINE_RE = /^>\s*⚠\s*Cap\/floor applied\s*—\s*review recommended\s*\n\n?/;

export function MarkdownAnswer({ payload }: { payload: FinalPayload }) {
  const cleanMarkdown = payload.capped
    ? payload.markdown.replace(CAP_LINE_RE, '')
    : payload.markdown;

  return (
    <div className="space-y-3">
      {payload.capped && <CapCallout />}
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
          {cleanMarkdown}
        </ReactMarkdown>
      </div>
    </div>
  );
}
