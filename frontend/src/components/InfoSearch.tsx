import { useState, useEffect } from 'react';
import { Check, ExternalLink, Search } from 'lucide-react';

const API_BASE = 'http://localhost:8000';

interface RelatedArticle {
  id: string;
  title: string;
  source: string;
  date: string;
  source_release_title?: string;
}

interface InfoSearchProps {
  pressReleaseId: string | null;
  selectedRefs: string[];
  onSelectRefs: (refs: string[]) => void;
}

export function InfoSearch(props: InfoSearchProps) {
  const { pressReleaseId, selectedRefs, onSelectRefs } = props;
  const [searchQuery, setSearchQuery] = useState('');
  const [articles, setArticles] = useState<RelatedArticle[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!pressReleaseId) {
      setArticles([]);
      return;
    }
    setLoading(true);
    fetch(`${API_BASE}/press-releases/related?ids=${encodeURIComponent(pressReleaseId)}`)
      .then((res) => res.json())
      .then((data) => {
        setArticles(data.related || []);
        setLoading(false);
      })
      .catch(() => {
        setArticles([]);
        setLoading(false);
      });
  }, [pressReleaseId]);

  const filtered = articles.filter(
    (a) =>
      !searchQuery ||
      a.title.includes(searchQuery) ||
      (a.source_release_title || '').includes(searchQuery) ||
      a.source.includes(searchQuery)
  );

  const toggleSelection = (id: string) => {
    onSelectRefs(selectedRefs.includes(id) ? selectedRefs.filter((i) => i !== id) : [...selectedRefs, id]);
  };

  const selectionBlock = selectedRefs.length > 0 ? (
    <div className="bg-white rounded-xl p-4 mb-4 border border-gray-200">
      <div className="text-xs text-gray-500 mb-2">{selectedRefs.length}개 참고자료 선택됨</div>
      <div className="flex flex-wrap gap-2">
        {selectedRefs.map((id) => {
          const article = articles.find((a) => a.id === id);
          return (
            <span key={id} className="px-2 py-1 bg-[#B4D88C]/20 text-[#4A5226] rounded text-[10px]">
              {article?.source} - {article?.date}
            </span>
          );
        })}
      </div>
    </div>
  ) : null;

  return (
    <div className="min-h-screen h-full overflow-auto bg-[#F5F5F0] p-8">
      <div className="max-w-[600px] mx-auto">
        <h2 className="text-2xl mb-2">참고 기사</h2>
        {pressReleaseId ? (
          <p className="text-sm text-gray-600 mb-6">선택한 보도자료와 관련된 과거 기사 및 참고 자료입니다.</p>
        ) : (
          <p className="text-sm text-gray-400 mb-6">먼저 보도자료를 선택해주세요.</p>
        )}

        <div className="flex gap-2 mb-6">
          <div className="flex-1 relative">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="참고 기사 검색..."
              className="w-full pl-9 pr-4 py-2.5 bg-white border border-gray-200 rounded-lg text-sm focus:outline-none focus:border-[#5C6832]"
            />
          </div>
          <button className="px-5 py-2.5 bg-[#5C6832] text-white rounded-lg text-sm hover:bg-[#4A5226] transition-all">
            검색
          </button>
        </div>

        {loading && <div className="text-center py-10 text-sm text-gray-400">참고 기사를 불러오는 중...</div>}
        {!loading && filtered.length > 0 && (
          <div className="space-y-3 mb-6">
            {filtered.map((article) => (
              <button
                key={article.id}
                onClick={() => toggleSelection(article.id)}
                className={
                  selectedRefs.includes(article.id)
                    ? 'w-full text-left p-5 rounded-xl border-2 transition-all bg-[#B4D88C]/20 border-[#5C6832]'
                    : 'w-full text-left p-5 rounded-xl border-2 transition-all bg-white border-gray-200 hover:border-[#B4D88C]'
                }
              >
                <div className="flex justify-between items-start">
                  <div className="flex-1">
                    {article.source_release_title && (
                      <div className="flex items-center gap-2 mb-1.5">
                        <span className="px-2 py-0.5 bg-[#B4D88C]/30 text-[#4A5226] rounded text-[10px]">
                          {article.source_release_title}
                        </span>
                      </div>
                    )}
                    <h4 className="text-sm mb-1">{article.title}</h4>
                    <div className="flex items-center gap-3 text-xs text-gray-500 mb-2">
                      <span>{article.source}</span>
                      <span>{article.date}</span>
                    </div>
                    <span className="text-[10px] text-[#5C6832] hover:underline inline-flex items-center gap-1">
                      원문 보기 <ExternalLink className="w-2.5 h-2.5" />
                    </span>
                  </div>
                  {selectedRefs.includes(article.id) && (
                    <Check className="w-5 h-5 text-[#5C6832] shrink-0 ml-3" strokeWidth={2.5} />
                  )}
                </div>
              </button>
            ))}
          </div>
        )}
        {!loading && filtered.length === 0 && pressReleaseId && (
          <div className="text-center py-10 text-sm text-gray-400">검색 결과가 없습니다.</div>
        )}
        {!loading && !pressReleaseId && (
          <div className="text-center py-20 text-sm text-gray-400">
            왼쪽 단계에서 보도자료를 먼저 선택하면
            <br />
            관련 참고 기사가 표시됩니다.
          </div>
        )}

        {selectionBlock}
      </div>
    </div>
  );
}
