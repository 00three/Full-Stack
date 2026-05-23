'use client';

import { useState, type ReactNode } from 'react';
import { ExternalLink, Info } from 'lucide-react';
import type { Citation } from '@/lib/api';

interface Props {
  body: string;
  citations: Record<string, Citation>;
  className?: string;
  fallbackCitationId?: string;
  appendFallbackWhenUncited?: boolean;
  paragraphInserts?: Record<number, ReactNode[]>;
}

export function BodyWithCitations({
  body,
  citations,
  className,
  fallbackCitationId = '1',
  appendFallbackWhenUncited = false,
  paragraphInserts,
}: Props) {
  if (!body) return null;

  const hasCitations = Object.keys(citations).length > 0;
  const baseClass =
    className ??
    'w-full text-[14px] sm:text-[15px] font-sans font-normal text-white/80 leading-[1.8] px-2 py-2 whitespace-pre-wrap';

  if (!hasCitations) {
    return <div className={baseClass}>{body}</div>;
  }

  const fallbackCitation = citations[fallbackCitationId];
  const paragraphs = body.split(/\n+/).filter((paragraph) => paragraph.trim().length > 0);

  const renderCitationParts = (text: string, keyPrefix: string) =>
    text.split(/(\[\d+\])/g).map((part, i) => {
      const match = part.match(/^\[(\d+)\]$/);
      if (match) {
        const id = match[1];
        const cite = citations[id];
        if (!cite) return <span key={`${keyPrefix}-${i}`}>{part}</span>;
        return <CitationIcon key={`${keyPrefix}-${i}-${id}`} citation={cite} />;
      }
      return <span key={`${keyPrefix}-${i}`}>{part}</span>;
    });

  return (
    <div className={baseClass}>
      {paragraphs.map((paragraph, idx) => {
        const hasParagraphCitation = /\[\d+\]/.test(paragraph);
        return (
          <div key={idx}>
            <p className={idx === 0 ? '' : 'mt-4'}>
              {renderCitationParts(paragraph, `p-${idx}`)}
              {appendFallbackWhenUncited && !hasParagraphCitation && fallbackCitation && (
                <CitationIcon citation={fallbackCitation} className="ml-2" />
              )}
            </p>
            {paragraphInserts?.[idx]?.map((insert, insertIdx) => (
              <div key={`insert-${idx}-${insertIdx}`} className="mt-4">
                {insert}
              </div>
            ))}
          </div>
        );
      })}
    </div>
  );
}

function CitationIcon({
  citation,
  className = 'ml-0.5',
}: {
  citation: Citation;
  className?: string;
}) {
  const [showTooltip, setShowTooltip] = useState(false);

  return (
    <span className="relative inline-flex align-middle">
      <span
        className={`inline-flex items-center justify-center w-5 h-5 rounded-full border border-white/25 bg-white/10 text-white/85 cursor-help hover:bg-white/25 hover:text-white transition-colors ${className}`}
        onMouseEnter={() => setShowTooltip(true)}
        onMouseLeave={() => setShowTooltip(false)}
        aria-label={`${citation.category} 출처 정보`}
      >
        <Info className="w-3 h-3" strokeWidth={2.5} />
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
