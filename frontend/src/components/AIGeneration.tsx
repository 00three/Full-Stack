import { useState, useEffect } from 'react';
import { FileText, Download, Sparkles, Save, Send, Info, ExternalLink } from 'lucide-react';

const API_BASE = 'http://localhost:8000';

interface Citation {
  category: string;
  title: string;
  date: string;
  url: string;
}

interface AIGenerationProps {
  pressReleaseId: string | null;
  referenceIds: string[];
}

/** 본문 텍스트에서 [1],[2] 출처 마커를 파싱해 아이콘+툴팁으로 렌더 */
function BodyWithCitations({
  body,
  citations,
  onChange,
}: {
  body: string;
  citations: Record<string, Citation>;
  onChange?: (value: string) => void;
}) {
  const parts = body.split(/(\[\d+\])/g);
  const isEditable = !!onChange;

  if (Object.keys(citations).length === 0) {
    return isEditable ? (
      <textarea
        value={body}
        onChange={(e) => onChange?.(e.target.value)}
        rows={12}
        className="w-full px-3 py-2.5 bg-gray-50 border border-gray-200 rounded-lg text-sm focus:outline-none focus:border-[#5C6832] resize-y"
      />
    ) : (
      <div className="w-full px-3 py-2.5 bg-gray-50 border border-gray-200 rounded-lg text-sm whitespace-pre-wrap">
        {body}
      </div>
    );
  }

  return (
    <div className="w-full min-h-[200px] px-3 py-2.5 bg-gray-50 border border-gray-200 rounded-lg text-sm whitespace-pre-wrap leading-relaxed">
      {parts.map((part, i) => {
        const match = part.match(/^\[(\d+)\]$/);
        if (match) {
          const id = match[1];
          const cite = citations[id];
          if (!cite) return null;
          return (
            <CitationIcon key={`${i}-${id}`} citation={cite} />
          );
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
        className="inline-flex items-center justify-center w-4 h-4 rounded-full bg-[#5C6832] text-white cursor-help ml-0.5"
        onMouseEnter={() => setShowTooltip(true)}
        onMouseLeave={() => setShowTooltip(false)}
      >
        <Info className="w-2.5 h-2.5" strokeWidth={2.5} />
      </span>
      {showTooltip && (
        <div
          className="absolute left-1/2 -translate-x-1/2 bottom-full mb-2 z-50 min-w-[220px] max-w-[280px] bg-white border border-gray-200 rounded-lg shadow-lg p-3"
          onMouseEnter={() => setShowTooltip(true)}
          onMouseLeave={() => setShowTooltip(false)}
        >
          <div className="absolute left-1/2 -translate-x-1/2 -bottom-2 w-4 h-4 bg-white border-r border-b border-gray-200 rotate-45" />
          <div className="text-[10px] text-[#5C6832] mb-1">{citation.category}</div>
          <div className="text-xs font-semibold text-gray-900 mb-1.5 leading-snug">{citation.title}</div>
          <div className="flex items-center justify-between text-[10px] text-gray-500">
            <span>{citation.date}</span>
            <a
              href={citation.url}
              target="_blank"
              rel="noreferrer"
              className="text-[#5C6832] hover:underline inline-flex items-center gap-0.5"
            >
              원문 보기 <ExternalLink className="w-3 h-3" />
            </a>
          </div>
        </div>
      )}
    </span>
  );
}

export function AIGeneration({ pressReleaseId, referenceIds }: AIGenerationProps) {
  const [title, setTitle] = useState('');
  const [lead, setLead] = useState('');
  const [body, setBody] = useState('');
  const [citations, setCitations] = useState<Record<string, Citation>>({});
  const [isGenerating, setIsGenerating] = useState(false);
  const [isGenerated, setIsGenerated] = useState(false);
  const [showExport, setShowExport] = useState(false);
  const [editMode, setEditMode] = useState(false);

  useEffect(() => {
    setIsGenerated(false);
    setIsGenerating(false);
    setShowExport(false);
    setEditMode(false);
  }, [pressReleaseId, referenceIds.length]);

  const handleGenerate = () => {
    if (!pressReleaseId) return;
    setIsGenerating(true);
    fetch(`${API_BASE}/articles/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        press_release_ids: [pressReleaseId],
        related_article_ids: referenceIds,
      }),
    })
      .then((res) => res.json())
      .then((data) => {
        setTitle(data.title || '');
        setLead(data.lead || '');
        setBody(data.body || '');
        setCitations(data.citations || {});
        setIsGenerated(true);
      })
      .catch(() => {
        setTitle('방통위, 소상공인 점포 정보 전송 서비스 2년 연장');
        setLead('방송통신위원회가 소상공인 점포 정보 전송 서비스의 사전동의 예외 허용을 2년 더 연장하기로 했다.');
        setBody(
          '이번 조치는 연 매출 10억 원 이하 소상공인의 경제 회복을 지원하기 위한 것이다.[1]\n\n해당 정책은 코로나19 확산 당시인 2022년 처음 도입됐으며 현재 약 2만 명의 이용자가 사용하고 있다.[1]'
        );
        setCitations({
          '1': {
            category: '방송통신위원회 보도자료',
            title: '소상공인 점포 정보 전송 서비스의 사전동의 예외 허용 기간 연장 발표문',
            date: '2026-03-19',
            url: 'https://www.kcc.go.kr/user.do?boardId=1113',
          },
        });
        setIsGenerated(true);
      })
      .finally(() => setIsGenerating(false));
  };

  const handleSave = () => {
    const content = `# ${title}\n\n${lead}\n\n${body}`;
    const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = title ? `${title.slice(0, 30).replace(/[/\\?%*:|"<>]/g, '-')}.md` : '기사.md';
    a.click();
    URL.revokeObjectURL(url);
  };

  const exportFormats = [
    { name: 'PDF', ext: '.pdf' },
    { name: 'HWP', ext: '.hwp' },
    { name: 'DOCX', ext: '.docx' },
    { name: 'TXT', ext: '.txt' },
    { name: 'HTML', ext: '.html' },
  ];

  const hasData = pressReleaseId && referenceIds.length > 0;

  return (
    <div className="min-h-screen h-full overflow-auto bg-[#F5F5F0] p-8">
      <div className="max-w-[600px] mx-auto">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-2xl">기사 편집기</h2>
          {isGenerated && (
            <button
              onClick={handleGenerate}
              disabled={isGenerating}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-[#B4D88C] text-[#4A5226] rounded-lg text-xs hover:bg-[#A8CC80] transition-all disabled:opacity-50"
            >
              <Sparkles className={`w-3 h-3 ${isGenerating ? 'animate-spin' : ''}`} />
              {isGenerating ? 'AI 생성 중...' : 'AI 재생성'}
            </button>
          )}
        </div>

        {!hasData && (
          <div className="text-center py-20 text-sm text-gray-400 mb-8">
            보도자료와 참고 기사를 선택하면
            <br />
            AI가 기사를 자동으로 생성합니다.
          </div>
        )}

        {hasData && !isGenerated && !isGenerating && (
          <div className="text-center py-20 mb-8">
            <p className="text-sm text-gray-500 mb-4">보도자료와 참고 기사가 선택되었습니다.</p>
            <button
              onClick={handleGenerate}
              className="relative inline-flex items-center gap-2 px-6 py-3 bg-[#5C6832] text-white rounded-lg text-sm hover:bg-[#4A5226] transition-all overflow-hidden before:absolute before:inset-0 before:bg-gradient-to-r before:from-transparent before:via-white/25 before:to-transparent before:-translate-x-full before:animate-[shimmer_2s_infinite]"
            >
              <span className="relative z-10 inline-flex items-center gap-2">
                <span className="animate-pulse">✦</span> AI 기사 생성
              </span>
            </button>
          </div>
        )}

        {hasData && isGenerating && (
          <div className="text-center py-20 mb-8">
            <Sparkles className="w-6 h-6 text-[#5C6832] animate-spin mx-auto mb-3" />
            <p className="text-sm text-gray-500">AI가 기사를 생성하고 있습니다...</p>
          </div>
        )}

        {hasData && isGenerated && !isGenerating && (
          <>
            <div className="bg-white rounded-2xl p-6 mb-6">
              <div className="mb-5">
                <label className="text-xs text-gray-500 mb-1.5 block">제목</label>
                <input
                  type="text"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  className="w-full px-3 py-2.5 bg-gray-50 border border-gray-200 rounded-lg text-sm focus:outline-none focus:border-[#5C6832]"
                />
              </div>
              <div className="mb-5">
                <label className="text-xs text-gray-500 mb-1.5 block">리드</label>
                <textarea
                  value={lead}
                  onChange={(e) => setLead(e.target.value)}
                  rows={3}
                  className="w-full px-3 py-2.5 bg-gray-50 border border-gray-200 rounded-lg text-sm focus:outline-none focus:border-[#5C6832] resize-none"
                />
              </div>
              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <label className="text-xs text-gray-500">본문</label>
                  {Object.keys(citations).length > 0 && (
                    <button
                      type="button"
                      onClick={() => setEditMode(!editMode)}
                      className="text-[10px] text-[#5C6832] hover:underline"
                    >
                      {editMode ? '출처 보기' : '편집'}
                    </button>
                  )}
                </div>
                {editMode ? (
                  <textarea
                    value={body}
                    onChange={(e) => setBody(e.target.value)}
                    rows={12}
                    className="w-full px-3 py-2.5 bg-gray-50 border border-gray-200 rounded-lg text-sm focus:outline-none focus:border-[#5C6832] resize-y"
                  />
                ) : (
                  <BodyWithCitations body={body} citations={citations} />
                )}
              </div>

              <div className="flex items-center justify-between mt-5 pt-4 border-t border-gray-100">
                <div className="relative">
                  <button
                    onClick={() => setShowExport(!showExport)}
                    className="flex items-center gap-1.5 px-3 py-2 bg-gray-100 text-gray-600 rounded-lg text-xs hover:bg-gray-200 transition-all"
                  >
                    <Download className="w-3.5 h-3.5" />
                    내보내기
                  </button>
                  {showExport && (
                    <div className="absolute bottom-full left-0 mb-2 bg-white border border-gray-200 rounded-lg shadow-lg p-2 z-50 flex flex-col gap-1 min-w-[120px]">
                      {exportFormats.map((format) => (
                        <button
                          key={format.name}
                          className="flex items-center gap-2 px-3 py-1.5 text-left text-xs text-gray-700 hover:bg-[#F0F4E4] hover:text-[#5C6832] rounded transition-all"
                        >
                          {format.name}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={handleSave}
                    className="flex items-center gap-1.5 px-4 py-2 bg-gray-100 text-gray-700 rounded-lg text-xs hover:bg-gray-200 transition-all"
                  >
                    <Save className="w-3.5 h-3.5" /> 저장
                  </button>
                  <button
                    disabled
                    title="CMS 연동 예정"
                    className="flex items-center gap-1.5 px-4 py-2 bg-gray-300 text-gray-500 rounded-lg text-xs cursor-not-allowed"
                  >
                    <Send className="w-3.5 h-3.5" /> 발행
                  </button>
                </div>
              </div>
            </div>
          </>
        )}

        <div className="mt-auto pt-8 text-center">
          <hr className="border-gray-300 mb-6" />
          <div className="inline-flex items-center gap-2 mb-2">
            <FileText className="w-4 h-4" />
            <span className="text-sm">NewsAI</span>
          </div>
          <div className="text-xs text-gray-500 space-y-1">
            <div>AI 기반 속보 콘텐츠 자동 생성 시스템</div>
            <div>© 2026 All rights reserved</div>
          </div>
        </div>
      </div>
    </div>
  );
}
