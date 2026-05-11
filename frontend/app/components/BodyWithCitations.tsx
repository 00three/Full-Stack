'use client';

import { useState } from 'react';
import { ExternalLink, Info } from 'lucide-react';
import type { Citation } from '@/lib/api';

interface Props {
  body: string;
  citations: Record<string, Citation>;
  className?: string;
}

export function BodyWithCitations({ body, citations, className }: Props) {
  if (!body) return null;

  const hasCitations = Object.keys(citations).length > 0;
  const baseClass =
    className ??
    'w-full text-[14px] sm:text-[15px] font-sans font-normal text-white/80 leading-[1.8] px-2 py-2 whitespace-pre-wrap';

  if (!hasCitations) {
    return <div className={baseClass}>{body}</div>;
  }

  const parts = body.split(/(\[\d+\])/g);

  return (
    <div className={baseClass}>
      {parts.map((part, i) => {
        const match = part.match(/^\[(\d+)\]$/);
        if (match) {
          const id = match[1];
          const cite = citations[id];
          if (!cite) return <span key={i}>{part}</span>;
          return <CitationIcon key={`${i}-${id}`} citation={cite} />;
        }
        return <span key={i}>{part}</span>;
      })}
    </div>
  );
}

function CitationIcon({ citation }: { citation: Citation }) {
  const [showTooltip, setShowTooltip] = useState(false);

  return (
    <span className="relative inline-flex align-middle">
      <span
        className="inline-flex items-center justify-center w-4 h-4 rounded-full bg-white/20 text-white cursor-help ml-0.5 hover:bg-white/40 transition-colors"
        onMouseEnter={() => setShowTooltip(true)}
        onMouseLeave={() => setShowTooltip(false)}
      >
        <Info className="w-2.5 h-2.5" strokeWidth={2.5} />
      </span>
      {showTooltip && (
        <div
          className="absolute left-1/2 -translate-x-1/2 bottom-full mb-2 z-50 min-w-[240px] max-w-[320px] bg-[#0a0a0a] border border-white/20 rounded-sm shadow-[0_0_30px_rgba(0,0,0,0.6)] p-3"
          onMouseEnter={() => setShowTooltip(true)}
          onMouseLeave={() => setShowTooltip(false)}
        >
          <div className="absolute left-1/2 -translate-x-1/2 -bottom-2 w-3 h-3 bg-[#0a0a0a] border-r border-b border-white/20 rotate-45" />
          <div className="text-[9px] uppercase tracking-[0.2em] text-accent mb-1.5">
            {citation.category}
          </div>
          <div className="text-xs font-semibold text-white mb-2 leading-snug">
            {citation.title}
          </div>
          <div className="flex items-center justify-between text-[10px] text-white/50">
            <span>{citation.date}</span>
            {citation.url ? (
              <a
                href={citation.url}
                target="_blank"
                rel="noreferrer"
                className="text-white/80 hover:text-white inline-flex items-center gap-0.5"
              >
                원문 보기 <ExternalLink className="w-3 h-3" />
              </a>
            ) : null}
          </div>
        </div>
      )}
    </span>
  );
}
