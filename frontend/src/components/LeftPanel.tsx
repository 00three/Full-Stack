import { Database, Search, Sparkles, Newspaper } from 'lucide-react';

interface LeftPanelProps {
  selectedSection: number;
  onSelectSection: (index: number) => void;
}

const steps = [
  { icon: Database, title: '보도자료', subtitle: '크롤링 선택', num: '01' },
  { icon: Search, title: '참고 기사', subtitle: '검색 · 검증', num: '02' },
  { icon: Sparkles, title: '기사 생성', subtitle: '편집 · 내보내기', num: '03' }
];

const sources = [
  { name: '방송통신위원회', type: '정부부처', content: '정책·규제·보도자료' },
  { name: '국회 동향 (NSP)', type: '국회도서관', content: '정책·입법 동향' },
  { name: '방송사 보도자료', type: 'MBC, SBS, KBS', content: '입장·정책 대응' },
  { name: '언론노조 성명', type: '노조', content: '성명·논평·보도자료' },
];

export function LeftPanel({ selectedSection, onSelectSection }: LeftPanelProps) {
  return (
    <div className="w-[358px] bg-[#4A5226] text-white px-7 py-5 flex flex-col justify-between h-screen fixed left-0 top-0">
      <div>
        <div className="flex items-center justify-between mb-8">
          <div className="flex items-center gap-2">
            <Newspaper className="w-5 h-5" strokeWidth={2} />
            <span className="text-sm">NewsAI</span>
          </div>
          <button className="px-4 py-1.5 bg-[#B4D88C] text-[#4A5226] rounded text-xs">
            시작하기
          </button>
        </div>

        <h1 className="text-[32px] leading-[1.2] mb-3">
          속보 콘텐츠
          <br />
          자동 생성 시스템
        </h1>

        <p className="text-xs mb-10 text-white/80">
          AI 기반 크롤링 데이터로 뉴스 기사를 자동 생성합니다.
        </p>

        <div className="mb-8">
          <h3 className="text-[10px] mb-4 tracking-wide text-white/50">작업 단계</h3>
          <div className="grid grid-cols-3 gap-2">
            {steps.map((step, index) => {
              const Icon = step.icon;
              const isSelected = selectedSection === index;
              return (
                <button
                  key={index}
                  onClick={() => onSelectSection(index)}
                  className={`aspect-square rounded-lg transition-all duration-300 flex flex-col items-center justify-center relative ${
                    isSelected ? 'bg-[#B4D88C] text-[#4A5226]' : 'bg-[#5C6832]/70 hover:bg-[#5C6832]'
                  }`}
                >
                  <span className={`text-[8px] absolute top-2 right-2 ${isSelected ? 'text-[#4A5226]/50' : 'text-white/30'}`}>{step.num}</span>
                  <Icon className="w-6 h-6 mb-2" strokeWidth={1.5} />
                  <div className="text-[10px]">{step.title}</div>
                  <div className={`text-[8px] ${isSelected ? 'text-[#4A5226]/60' : 'text-white/50'}`}>{step.subtitle}</div>
                </button>
              );
            })}
          </div>
        </div>

        <div className="mt-8">
          <h3 className="text-[10px] mb-3 tracking-wide text-white/50">수집 소스</h3>
          <div className="space-y-0 rounded-lg overflow-hidden border border-white/10">
            <div className="grid grid-cols-[1fr_0.8fr_1fr] bg-white/10 px-3 py-2 text-[9px] text-white/50">
              <span>소스</span>
              <span>성격</span>
              <span>내용</span>
            </div>
            {sources.map((src, i) => (
              <div key={i} className="grid grid-cols-[1fr_0.8fr_1fr] px-3 py-2.5 text-[10px] border-t border-white/5">
                <span className="text-white/90">{src.name}</span>
                <span className="text-white/50">{src.type}</span>
                <span className="text-[#B4D88C]/80">{src.content}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      <div>
        <div className="flex gap-4 text-[10px] text-white/50">
          <a href="#" className="hover:underline hover:text-white/80">문의</a>
          <a href="#" className="hover:underline hover:text-white/80">소셜</a>
          <a href="#" className="hover:underline hover:text-white/80">이용약관</a>
          <a href="#" className="hover:underline hover:text-white/80">개인정보</a>
        </div>
      </div>
    </div>
  );
}
