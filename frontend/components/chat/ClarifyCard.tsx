'use client';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { FinalPayload } from '@/types/agent.types';

export function ClarifyCard({ payload }: { payload: FinalPayload }) {
  return (
    <div className="rounded border border-blue-200 bg-blue-50 p-4">
      <h3 className="text-base font-semibold text-blue-900">
        I need a bit more info
      </h3>
      <div className="prose prose-sm mt-2 max-w-none text-blue-900">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>
          {payload.markdown}
        </ReactMarkdown>
      </div>
    </div>
  );
}
