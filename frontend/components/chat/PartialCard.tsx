'use client';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { MarkdownAnswer } from '@/components/chat/MarkdownAnswer';
import type { FinalPayload } from '@/types/agent.types';

export function PartialCard({ payload }: { payload: FinalPayload }) {
  return (
    <div className="space-y-3 rounded border border-orange-200 bg-orange-50 p-4">
      <h3 className="text-base font-semibold text-orange-900">Limited result</h3>
      {payload.surcharge_result != null ? (
        <MarkdownAnswer payload={payload} />
      ) : (
        <div className="prose prose-sm max-w-none text-orange-900">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {payload.markdown}
          </ReactMarkdown>
        </div>
      )}
    </div>
  );
}
