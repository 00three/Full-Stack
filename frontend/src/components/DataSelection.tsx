import { useState, useEffect } from 'react';
import { Check, ExternalLink, RefreshCw, Clock, Search, Calendar } from 'lucide-react';

const API_BASE = 'http://localhost:8000';

interface PressRelease {
  id: string;
  title: string;
  source: string;
  date: string;
  summary?: string;
  detail_url: string;
  is_new?: boolean;
}

interface DataSelectionProps {
  selectedId: string | null;
  onSelect: (id: string) => void;
  onNext: () => void;
  onRefresh: () => void;
}

export function DataSelection({ selectedId, onSelect, onNext, onRefresh }: DataSelectionProps) {
  const [searchInput, setSearchInput] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [items, setItems] = useState<PressRelease[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    const url = searchQuery
      ? `${API_BASE}/press-releases?q=${encodeURIComponent(searchQuery)}`
      : `${API_BASE}/press-releases`;
    fetch(url)
      .then((res) => res.json())
      .then((data) => {
        setItems(data);
        setLoading(false);
      })
      .catch(() => {
        setItems([]);
        setLoading(false);
      });
  }, [searchQuery]);

  const filtered = items.filter((item) => {
    const matchesFrom = !dateFrom || item.date >= dateFrom;
    const matchesTo = !dateTo || item.date <= dateTo;
    return matchesFrom && matchesTo;
  });

  const handleRefresh = () => {
    setSearchInput('');
    setSearchQuery('');
    setDateFrom('');
    setDateTo('');
    onRefresh();
    setLoading(true);
    fetch(`${API_BASE}/press-releases`)
      .then((res) => res.json())
      .then((data) => {
        setItems(data);
        setLoading(false);
      })
      .catch(() => setLoading(false));
  };

  return (
    <div className="min-h-screen h-full overflow-auto bg-[#F5F5F0] p-8">
      <div className="max-w-[600px] mx-auto">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h2 className="text-2xl mb-1">최신 보도자료</h2>
            <div className="flex items-center gap-2 text-xs text-gray-500">
              <Clock className="w-3 h-3" />
              <span>마지막 업데이트: 2026-03-19 09:30</span>
            </div>
          </div>
          <button
            onClick={handleRefresh}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-[#B4D88C] text-[#4A5226] rounded-lg text-xs hover:bg-[#A8CC80] transition-all"
          >
            <RefreshCw className="w-3 h-3" />
            새로고침
          </button>
        </div>

        <div className="space-y-3 mb-6">
          <div className="flex gap-2">
            <div className="flex-1 relative">
              <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
              <input
                type="text"
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && setSearchQuery(searchInput.trim())}
                placeholder="최신 보도자료 검색..."
                className="w-full pl-9 pr-4 py-2.5 bg-white border border-gray-200 rounded-lg text-sm focus:outline-none focus:border-[#5C6832]"
              />
            </div>
            <button
              onClick={() => setSearchQuery(searchInput.trim())}
              className="px-5 py-2.5 bg-[#5C6832] text-white rounded-lg text-sm hover:bg-[#4A5226] transition-all"
            >
              검색
            </button>
          </div>
          <div className="flex items-center gap-2">
            <label className="flex items-center gap-1.5 px-3 py-1.5 bg-white border border-gray-200 rounded-lg cursor-pointer hover:border-[#5C6832] transition-all">
              <Calendar className="w-3.5 h-3.5 text-[#5C6832]" />
              <span className="text-xs text-gray-600">{dateFrom || '시작일'}</span>
              <input
                type="date"
                value={dateFrom}
                onChange={(e) => setDateFrom(e.target.value)}
                className="sr-only"
              />
            </label>
            <span className="text-xs text-gray-400">~</span>
            <label className="flex items-center gap-1.5 px-3 py-1.5 bg-white border border-gray-200 rounded-lg cursor-pointer hover:border-[#5C6832] transition-all">
              <Calendar className="w-3.5 h-3.5 text-[#5C6832]" />
              <span className="text-xs text-gray-600">{dateTo || '종료일'}</span>
              <input
                type="date"
                value={dateTo}
                onChange={(e) => setDateTo(e.target.value)}
                className="sr-only"
              />
            </label>
          </div>
        </div>

        <div className="space-y-3">
          {loading && <div className="text-center py-10 text-sm text-gray-400">로딩 중...</div>}
          {!loading &&
            filtered.map((item) => (
              <button
                key={item.id}
                onClick={() => onSelect(item.id)}
                className={`w-full text-left p-5 rounded-xl border-2 transition-all ${
                  selectedId === item.id ? 'bg-[#B4D88C]/20 border-[#5C6832]' : 'bg-white border-gray-200 hover:border-[#B4D88C]'
                }`}
              >
                <div className="flex justify-between items-start">
                  <div className="flex-1">
                    <div className="flex items-start gap-2 mb-1.5">
                      {item.is_new && (
                        <span className="shrink-0 inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold text-white bg-red-500 animate-new-badge">
                          NEW
                        </span>
                      )}
                      <h3 className="text-sm font-semibold flex-1 min-w-0">{item.title}</h3>
                    </div>
                    <div className="flex gap-3 text-xs text-gray-500 mb-2">
                      <span className="text-[#5C6832]">{item.source}</span>
                      <span>{item.date}</span>
                    </div>
                    {item.summary && <p className="text-xs text-gray-600 mb-2">{item.summary}</p>}
                    <a
                      href={item.detail_url}
                      target="_blank"
                      rel="noreferrer"
                      className="text-xs text-[#5C6832] hover:underline inline-flex items-center gap-1"
                      onClick={(e) => e.stopPropagation()}
                    >
                      원문 보기 <ExternalLink className="w-3 h-3" />
                    </a>
                  </div>
                  {selectedId === item.id && <Check className="w-5 h-5 text-[#5C6832] shrink-0 ml-3" strokeWidth={2.5} />}
                </div>
              </button>
            ))}
          {!loading && filtered.length === 0 && <div className="text-center py-10 text-sm text-gray-400">검색 결과가 없습니다.</div>}
        </div>

        <div className="flex justify-center gap-6 mt-8 mb-4 text-[10px] text-gray-400">
          <span>연합뉴스</span>
          <span>뉴스와이어</span>
          <span>정책브리핑</span>
          <span>국회뉴스</span>
          <span>공정위</span>
        </div>

        {selectedId && (
          <button
            onClick={onNext}
            className="w-full mt-4 px-6 py-3 bg-[#5C6832] text-white rounded-lg hover:bg-[#4A5226] transition-all text-sm"
          >
            관련 정보 검색하기 →
          </button>
        )}
      </div>
    </div>
  );
}
