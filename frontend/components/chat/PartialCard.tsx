'use client';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { MarkdownAnswer } from '@/components/chat/MarkdownAnswer';
import type { FinalPayload } from '@/types/agent.types';

export function PartialCard({ payload }: { payload: FinalPayload }) {
  return (
    <div className="space-y-3 rounded glass-surface border-orange-200 border-orange-300/30 bg-orange-50 bg-orange-500/10 p-4">
      <h3 className="text-base font-semibold text-orange-200">Limited result</h3>
      {payload.surcharge_result != null ? (
        <MarkdownAnswer payload={payload} />
      ) : (
        <div className="prose prose-sm prose-invert max-w-none text-orange-100">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {payload.markdown}
          </ReactMarkdown>
        </div>
      )}
    </div>
  );
}
