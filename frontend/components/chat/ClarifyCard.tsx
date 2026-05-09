'use client';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { FinalPayload } from '@/types/agent.types';

export function ClarifyCard({ payload }: { payload: FinalPayload }) {
  return (
    <div className="rounded glass-surface border-blue-200 border-blue-300/30 bg-blue-50 bg-blue-500/10 p-4">
      <h3 className="text-base font-semibold text-blue-100">
        I need a bit more info
      </h3>
      <div className="prose prose-sm prose-invert mt-2 max-w-none text-blue-100">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>
          {payload.markdown}
        </ReactMarkdown>
      </div>
    </div>
  );
}
