import React, { useState, useEffect, useRef, useMemo } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import confetti from 'canvas-confetti';
import {
  Search, RefreshCcw, ExternalLink,
  ChevronRight, ArrowRight, Download, FileText,
  Info
} from 'lucide-react';
import {
  fetchPressReleases,
  fetchRelatedArticles,
  generateArticle,
  type PressRelease,
  type RelatedArticle,
  type GeneratedArticle,
} from '@/lib/api';
import { BodyWithCitations } from './BodyWithCitations';

function sortPressReleases(items: PressRelease[]): PressRelease[] {
  return [...items].sort((a, b) => {
    if (a.isNew === b.isNew) {
      return new Date(b.date).getTime() - new Date(a.date).getTime();
    }
    return a.isNew ? -1 : 1;
  });
}

// --- Components ---

type LogoConfig = {
  src: string;
  className: string;
  fallback: string;
};

const SourceLogo = ({ source }: { source: string }) => {
  const logos: Record<string, LogoConfig> = {
    '방송통신위원회': {
      src: '/logos/kcc.png?v=20260428-white',
      className: 'h-5 sm:h-6 max-w-[145px] sm:max-w-[175px] w-auto opacity-95 drop-shadow-[0_0_3px_rgba(255,255,255,0.25)]',
      fallback: 'bg-white px-1.5 py-0.5 rounded-sm text-black font-bold text-[9px]'
    },
    'MBC': {
      src: '/logos/03_mbc_logo.png',
      className: 'h-4 sm:h-5 max-w-[70px] w-auto object-contain brightness-0 invert opacity-90 drop-shadow-[0_0_3px_rgba(255,255,255,0.35)]',
      fallback: 'bg-[#1a1a1a] border border-white/20 text-white px-1.5 py-0.5 font-bold tracking-widest text-[9px] rounded-sm'
    },
    '언론노조': {
      src: '/logos/언론노조.png?v=20260428-union-white',
      className: 'h-5 sm:h-6 max-w-[145px] sm:max-w-[165px] w-auto object-contain drop-shadow-[0_0_3px_rgba(255,255,255,0.25)]',
      fallback: 'bg-[#b91c1c] text-white px-1.5 py-0.5 font-bold tracking-widest text-[9px] rounded-sm flex items-center gap-1 shadow-sm'
    },
    '국회도서관': {
      src: '/logos/02_nsp_nail_logo_white.png',
      className: 'h-5 sm:h-6 max-w-[64px] w-auto object-contain opacity-95',
      fallback: 'bg-[#1d4ed8] text-white px-1.5 py-0.5 font-bold text-[9px] rounded-sm shadow-sm'
    },
    'NSP': {
      src: '/logos/02_nsp_nail_logo_white.png',
      className: 'h-5 sm:h-6 max-w-[64px] w-auto object-contain opacity-95',
      fallback: 'bg-[#1d4ed8] text-white px-1.5 py-0.5 font-bold text-[9px] rounded-sm shadow-sm'
    },
    'KCC': {
      src: '/logos/kcc.png?v=20260428-white',
      className: 'h-5 sm:h-6 max-w-[145px] sm:max-w-[175px] w-auto opacity-95 drop-shadow-[0_0_3px_rgba(255,255,255,0.25)]',
      fallback: 'bg-white px-1.5 py-0.5 rounded-sm text-black font-bold text-[9px]'
    },
    'NODONG': {
      src: '/logos/언론노조.png?v=20260428-union-white',
      className: 'h-5 sm:h-6 max-w-[145px] sm:max-w-[165px] w-auto object-contain drop-shadow-[0_0_3px_rgba(255,255,255,0.25)]',
      fallback: 'bg-[#b91c1c] text-white px-1.5 py-0.5 font-bold tracking-widest text-[9px] rounded-sm flex items-center gap-1 shadow-sm'
    }
  };

  const logo = logos[source];
  
  if (logo?.src) {
    return (
      <div className="shrink-0 flex items-center justify-center">
        <img src={logo.src} alt={source} className={`object-contain ${logo.className}`} />
      </div>
    );
  }

  if (logo?.fallback) {
     return (
        <span className={`${logo.fallback} shrink-0`}>
          {(source === '언론노조' || source === 'NODONG') && <span className="text-[10px] leading-none -mt-0.5">✊</span>}
          {source}
        </span>
     );
  }

  return <span className="text-[9px] font-sans uppercase tracking-[0.2em] text-accent border border-white/20 px-2 py-0.5 bg-white/5 shrink-0">{source}</span>;
};

const Butterfly = ({ className }: { className?: string }) => (
  <svg className={className} viewBox="0 0 100 100" fill="currentColor" xmlns="http://www.w3.org/2000/svg">
    {/* Antennae */}
    <path d="M 48 30 Q 40 10 30 15" stroke="currentColor" strokeWidth="1.5" fill="none" strokeLinecap="round" />
    <path d="M 52 30 Q 60 10 70 15" stroke="currentColor" strokeWidth="1.5" fill="none" strokeLinecap="round" />
    {/* Body */}
    <path d="M 48 30 Q 50 25 52 30 L 53 60 Q 50 70 47 60 Z" fillOpacity="0.9" />
    {/* Wings */}
    <path d="M 48 35 C 30 15 5 15 5 35 C 5 50 20 55 47 45 Z" fillOpacity="0.8" />
    <path d="M 47 45 C 30 55 15 75 25 85 C 35 95 45 75 49 55 Z" fillOpacity="0.6" />
    <path d="M 52 35 C 70 15 95 15 95 35 C 95 50 80 55 53 45 Z" fillOpacity="0.8" />
    <path d="M 53 45 C 70 55 85 75 75 85 C 65 95 55 75 51 55 Z" fillOpacity="0.6" />
  </svg>
);

const AmbientButterflies = () => {
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  const butterflies = useMemo(() => Array.from({ length: 14 }).map((_, i) => {
    const zones = ['left', 'right', 'top', 'bottom'];
    const zone = zones[i % 4];
    
    const xPoints: number[] = [];
    const yPoints: number[] = [];
    const rPoints: number[] = [];
    let currentR = Math.random() * 360;

    for(let j=0; j<6; j++) {
      if (zone === 'left') {
        xPoints.push(Math.random() * 25 - 5); // -5 to 20vw
        yPoints.push(Math.random() * 110 - 5);
      } else if (zone === 'right') {
        xPoints.push(75 + Math.random() * 30); // 75 to 105vw
        yPoints.push(Math.random() * 110 - 5);
      } else if (zone === 'top') {
        xPoints.push(Math.random() * 110 - 5);
        yPoints.push(Math.random() * 20 - 5); // -5 to 15vh
      } else { // bottom
        xPoints.push(Math.random() * 110 - 5);
        yPoints.push(85 + Math.random() * 20); // 85 to 105vh
      }
      rPoints.push(currentR);
      currentR += (Math.random() * 180 - 90); // Drift rotation slowly
    }
    
    // Link back to start for smooth endless loop
    xPoints.push(xPoints[0]);
    yPoints.push(yPoints[0]);
    rPoints.push(currentR);

    const duration = Math.random() * 100 + 80; // 80-180s very slow, random path
    
    return {
      id: i,
      xPoints,
      yPoints,
      rPoints,
      duration,
      delay: -(Math.random() * duration), // Start scattered along the path
      scale: Math.random() * 0.4 + 0.3,
      flutterDuration: Math.random() * 0.5 + 0.4, // Slow, graceful flap
    };
  }), []);

  if (!mounted) return null;

  return (
    <div className="absolute inset-0 pointer-events-none z-0 overflow-hidden mix-blend-screen opacity-40">
      {butterflies.map((b) => (
        <motion.div
          key={b.id}
          className="absolute blur-[0.2px]"
          initial={{
            x: `${b.xPoints[0]}vw`,
            y: `${b.yPoints[0]}vh`,
            rotate: b.rPoints[0],
            scale: b.scale,
          }}
          animate={{
            x: b.xPoints.map(v => `${v}vw`),
            y: b.yPoints.map(v => `${v}vh`),
            rotate: b.rPoints,
          }}
          transition={{
            x: { duration: b.duration, repeat: Infinity, ease: "linear", delay: b.delay },
            y: { duration: b.duration, repeat: Infinity, ease: "linear", delay: b.delay },
            rotate: { duration: b.duration, repeat: Infinity, ease: "linear", delay: b.delay },
          }}
        >
          <motion.div
            animate={{ 
              scaleX: [1, 0.4, 0.8, 1], 
              y: [0, -15, 5, -10, 0], // Graceful bobbing
              rotate: [0, 5, -5, 0] // Gentle wavering
            }}
            transition={{ 
              scaleX: { duration: b.flutterDuration, repeat: Infinity, ease: "easeInOut" },
              y: { duration: Math.random() * 6 + 6, repeat: Infinity, ease: "easeInOut" },
              rotate: { duration: Math.random() * 5 + 5, repeat: Infinity, ease: "easeInOut" }
            }}
          >
            <Butterfly className="w-20 h-20 drop-shadow-[0_0_12px_rgba(255,255,255,0.5)] text-accent/70" />
          </motion.div>
        </motion.div>
      ))}
    </div>
  );
};

export default function NewsDashboard() {
  const [step, setStep] = useState<0 | 1 | 2 | 3 | 4>(0);
  const [reporterInfo, setReporterInfo] = useState({ media: '', name: '' });
  const [pressReleases, setPressReleases] = useState<PressRelease[]>([]);
  const [isLoadingPRs, setIsLoadingPRs] = useState(true);
  const [prsError, setPrsError] = useState<string | null>(null);
  const [selectedPR, setSelectedPR] = useState<PressRelease | null>(null);
  const [relatedArticles, setRelatedArticles] = useState<RelatedArticle[]>([]);
  const [isLoadingRelated, setIsLoadingRelated] = useState(false);
  const [selectedArticles, setSelectedArticles] = useState<RelatedArticle[]>([]);
  const [isGenerating, setIsGenerating] = useState(false);
  const [generated, setGenerated] = useState<GeneratedArticle | null>(null);
  const [generateError, setGenerateError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<string>('');
  const [isEditing, setIsEditing] = useState(false);
  const stepRefs = useRef<(HTMLSpanElement | null)[]>([]);

  useEffect(() => {
    const now = new Date();
    setLastUpdated(now.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' }));
  }, []);

  useEffect(() => {
    let cancelled = false;
    setIsLoadingPRs(true);
    setPrsError(null);
    fetchPressReleases()
      .then((items) => {
        if (cancelled) return;
        setPressReleases(sortPressReleases(items));
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setPrsError(err instanceof Error ? err.message : '보도자료를 불러오지 못했습니다');
        setPressReleases([]);
      })
      .finally(() => {
        if (!cancelled) setIsLoadingPRs(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const triggerConfettiFromStep = (stepIndex: number) => {
    const el = stepRefs.current[stepIndex];
    if (el) {
      const rect = el.getBoundingClientRect();
      const originX = (rect.left + rect.width / 2) / window.innerWidth;
      const originY = (rect.top + rect.height / 2) / window.innerHeight;
      
      confetti({
        particleCount: 60,
        spread: 80,
        origin: { x: originX, y: originY },
        colors: ['#ffffff', '#8e8e8e', '#cccccc'],
        zIndex: 9999,
        disableForReducedMotion: true,
        startVelocity: 25,
        scalar: 0.8,
        ticks: 150
      });
    } else {
      confetti({
        particleCount: 80,
        spread: 60,
        origin: { x: 0.5, y: 0.8 },
        colors: ['#ffffff', '#8e8e8e', '#cccccc'],
        zIndex: 9999,
        disableForReducedMotion: true
      });
    }
  };

  const goToStep = (newStep: 0 | 1 | 2 | 3 | 4) => {
    if (newStep > step && newStep !== 3 && newStep !== 4 && step !== 0) {
      triggerConfettiFromStep(step);
    }
    setStep(newStep);
  };

  const handleStartWithProfile = () => {
    setReporterInfo({
      media: reporterInfo.media || '미디어스',
      name: reporterInfo.name || '김홍근'
    });
    goToStep(1);
  };

  const handleSelectPR = (pr: PressRelease) => {
    setSelectedPR(pr);
    setSelectedArticles([]);
    setRelatedArticles([]);
    setIsLoadingRelated(true);
    fetchRelatedArticles(pr.id)
      .then((items) => setRelatedArticles(items))
      .catch(() => setRelatedArticles([]))
      .finally(() => setIsLoadingRelated(false));
    goToStep(2);
  };

  const toggleArticle = (article: RelatedArticle) => {
    setSelectedArticles(prev =>
      prev.find(a => a.id === article.id)
        ? prev.filter(a => a.id !== article.id)
        : [...prev, article]
    );
  };

  const handleGenerate = () => {
    if (!selectedPR) return;
    setIsGenerating(true);
    setGenerateError(null);
    generateArticle(
      [selectedPR.id],
      selectedArticles.map((a) => a.id),
    )
      .then((article) => {
        setGenerated(article);
        setStep(4);
      })
      .catch((err: unknown) => {
        setGenerateError(err instanceof Error ? err.message : '기사 생성에 실패했습니다');
      })
      .finally(() => setIsGenerating(false));
  };

  return (
    <section className="min-h-screen bg-bg text-ink pt-12 pb-24 px-4 sm:px-6 selection:bg-white/20 relative overflow-hidden">
      {/* Subtle ambient background glow */}
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 w-[600px] h-[600px] bg-white/[0.015] rounded-full blur-[100px] pointer-events-none" />

      <AmbientButterflies />

      <div className="max-w-6xl mx-auto w-full relative z-10">
        
        {/* Top Header / Breadcrumbs */}
        {step >= 1 && (
          <motion.header 
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, ease: "easeOut" }}
            className="mb-8 flex justify-center border-b border-white/10 pb-5"
          >
            <div className="flex items-center gap-3 sm:gap-5 lg:gap-8 text-sm sm:text-lg md:text-xl font-serif tracking-[0.05em] justify-center text-white/40">
              <span ref={(el) => { stepRefs.current[1] = el; }} className={`transition-all duration-500 cursor-pointer ${step >= 1 ? 'text-ink drop-shadow-[0_0_8px_rgba(255,255,255,0.3)] font-bold' : 'hover:text-white'}`} onClick={() => step > 1 && goToStep(1)}>1. 소스 선택</span>
              <ChevronRight className={`w-3.5 h-3.5 md:w-5 md:h-5 transition-colors duration-500 ${step >= 2 ? 'text-accent' : 'text-white/10'}`} />
              <span ref={(el) => { stepRefs.current[2] = el; }} className={`transition-all duration-500 cursor-pointer ${step >= 2 ? 'text-ink drop-shadow-[0_0_8px_rgba(255,255,255,0.3)] font-bold' : 'hover:text-white'}`} onClick={() => step > 2 && goToStep(2)}>2. 관련 기사</span>
              <ChevronRight className={`w-3.5 h-3.5 md:w-5 md:h-5 transition-colors duration-500 ${step >= 3 ? 'text-accent' : 'text-white/10'}`} />
              <span ref={(el) => { stepRefs.current[3] = el; }} className={`transition-all duration-500 cursor-pointer ${step >= 3 ? 'text-ink drop-shadow-[0_0_8px_rgba(255,255,255,0.3)] font-bold' : 'hover:text-white'}`} onClick={() => step > 3 && goToStep(3)}>3. 생성 설정</span>
              <ChevronRight className={`w-3.5 h-3.5 md:w-5 md:h-5 transition-colors duration-500 ${step === 4 ? 'text-accent' : 'text-white/10'}`} />
              <span ref={(el) => { stepRefs.current[4] = el; }} className={`transition-all duration-500 ${step === 4 ? 'text-ink drop-shadow-[0_0_12px_rgba(255,255,255,0.4)] font-bold' : ''}`}>4. 결과물</span>
            </div>
          </motion.header>
        )}

        <AnimatePresence mode="wait">
          {/* STEP 0: REPORTER PROFILE SETUP */}
          {step === 0 && (
            <motion.div
                key="step-0"
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 1.05 }}
                className="max-w-md mx-auto mt-10 sm:mt-20 p-8 border border-white/10 bg-[#0a0a0a] shadow-[0_0_40px_rgba(0,0,0,0.5)] rounded-sm space-y-6 relative overflow-hidden"
            >
                {/* Subtle top light */}
                <div className="absolute top-0 left-1/2 -translate-x-1/2 w-3/4 h-[1px] bg-gradient-to-r from-transparent via-white/50 to-transparent" />

                <div className="space-y-2 text-center pb-2">
                  <h2 className="text-xl sm:text-2xl font-serif tracking-widest font-bold text-white">기자 프로필 설정</h2>
                  <p className="text-xs font-sans text-white/50 tracking-wide">기사 송고 전 사용할 기본 프로필 정보를 입력해주세요.</p>
                </div>
                
                <div className="space-y-5 pt-4">
                  <div className="space-y-2 group">
                      <label className="text-[10px] uppercase tracking-[0.2em] font-sans text-accent group-focus-within:text-white transition-colors">매체명</label>
                      <input 
                        type="text" 
                        value={reporterInfo.media}
                        onChange={(e) => setReporterInfo({...reporterInfo, media: e.target.value})}
                        className="w-full bg-white/[0.03] border border-white/20 text-white p-3 font-sans outline-none focus:border-white/50 focus:bg-white/[0.06] transition-all rounded-sm placeholder:text-white/30"
                        placeholder="예: 미디어스"
                      />
                  </div>
                  <div className="space-y-2 group">
                      <label className="text-[10px] uppercase tracking-[0.2em] font-sans text-accent group-focus-within:text-white transition-colors">기자명</label>
                      <input 
                        type="text" 
                        value={reporterInfo.name}
                        onChange={(e) => setReporterInfo({...reporterInfo, name: e.target.value})}
                        className="w-full bg-white/[0.03] border border-white/20 text-white p-3 font-sans outline-none focus:border-white/50 focus:bg-white/[0.06] transition-all rounded-sm placeholder:text-white/30"
                        placeholder="예: 김홍근"
                      />
                  </div>
                  
                  <button 
                      onClick={handleStartWithProfile}
                      className="w-full py-4 mt-6 bg-white text-black font-bold text-[11px] uppercase tracking-[0.2em] hover:bg-gray-200 transition-all rounded-sm flex items-center justify-center gap-2 group/btn shadow-[0_0_15px_rgba(255,255,255,0.2)] hover:shadow-[0_0_25px_rgba(255,255,255,0.4)]"
                  >
                      {reporterInfo.media || reporterInfo.name ? '설정 및 시작하기' : '기본 예시로 시작하기'} <ArrowRight className="w-4 h-4 group-hover/btn:translate-x-1 transition-transform" />
                  </button>
                </div>
            </motion.div>
          )}

          {/* STEP 1: SOURCE SELECTION */}
          {step === 1 && (
            <motion.div
              key="step-1"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20, transition: { duration: 0.3 } }}
              transition={{ duration: 0.6, ease: [0.16, 1, 0.3, 1] }}
              className="space-y-4"
            >
              <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3">
                <div className="flex items-center gap-3">
                  <h3 className="text-xl sm:text-2xl font-serif tracking-widest uppercase font-bold text-white/90">최신 보도자료</h3>
                  <button className="flex items-center gap-1.5 text-[10px] tracking-[0.1em] font-sans text-accent bg-white/5 border border-white/10 px-2 py-1 hover:bg-white/10 hover:text-ink transition-all duration-300 rounded-sm" onClick={() => setLastUpdated(new Date().toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' }))}>
                    <RefreshCcw className="w-2.5 h-2.5" />
                    업데이트 : {lastUpdated}
                  </button>
                </div>
                <div className="relative w-full sm:w-64 group">
                  <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-accent group-focus-within:text-ink transition-colors" />
                  <input type="text" placeholder="검색어 입력..." className="w-full bg-white/[0.02] border border-white/10 text-ink text-xs pl-9 pr-3 py-2 outline-none focus:border-white/40 focus:bg-white/[0.05] transition-all placeholder:text-white/20 rounded-sm" />
                </div>
              </div>

              <div className="space-y-2.5">
                {isLoadingPRs && (
                  <div className="text-center py-10 text-[11px] font-sans uppercase tracking-[0.2em] text-white/40">
                    보도자료 불러오는 중...
                  </div>
                )}
                {!isLoadingPRs && prsError && (
                  <div className="text-center py-10 text-[11px] font-sans uppercase tracking-[0.2em] text-red-400/80">
                    {prsError}
                  </div>
                )}
                {!isLoadingPRs && !prsError && pressReleases.length === 0 && (
                  <div className="text-center py-10 text-[11px] font-sans uppercase tracking-[0.2em] text-white/40">
                    보도자료가 없습니다
                  </div>
                )}
                {!isLoadingPRs && pressReleases.map((pr, idx) => (
                  <motion.div
                    key={pr.id}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.4, delay: idx * 0.05, ease: "easeOut" }}
                    onClick={() => handleSelectPR(pr)}
                    className="group relative bg-white/[0.015] border border-white/10 hover:bg-white/[0.04] hover:border-white/30 transition-all duration-300 p-3 sm:py-3 sm:px-4 flex flex-col sm:flex-row gap-3 items-start sm:items-center cursor-pointer overflow-hidden rounded-[2px]"
                  >
                    <div className="absolute left-0 top-0 bottom-0 w-[3px] bg-white/0 group-hover:bg-white/40 transition-colors duration-300" />

                    <div className="flex-1 space-y-1.5 w-full pl-1.5">
                      <div className="flex items-center gap-2.5">
                        {pr.isNew && (
                          <motion.span
                            initial={{ opacity: 0 }}
                            animate={{ opacity: [0.7, 1, 0.7] }}
                            transition={{ duration: 2, repeat: Infinity, ease: "easeInOut" }}
                            className="text-[9px] uppercase tracking-[0.2em] bg-red-600/80 border border-red-500/50 text-white px-1.5 py-0.5 font-bold rounded-[2px] relative overflow-hidden"
                          >
                            <span className="relative z-10">New</span>
                          </motion.span>
                        )}
                        <SourceLogo source={pr.source} />
                        <span className="text-[9px] font-sans uppercase tracking-[0.2em] text-accent/70">{pr.date}</span>
                      </div>
                      <h4 className="text-[17px] sm:text-[19px] font-sans font-[700] text-white/90 group-hover:text-white transition-colors tracking-tight leading-snug drop-shadow-sm">{pr.title}</h4>
                      <p className="text-[13px] font-sans font-normal text-white/60 max-w-4xl leading-relaxed line-clamp-2">{pr.summary}</p>
                    </div>
                    <div className="flex gap-2 sm:flex-col items-end sm:w-24 opacity-40 group-hover:opacity-100 transition-opacity justify-center h-full">
                      {pr.detail_url ? (
                        <a
                          href={pr.detail_url}
                          target="_blank"
                          rel="noreferrer"
                          onClick={(e) => e.stopPropagation()}
                          className="text-[9px] uppercase tracking-[0.2em] font-sans text-ink flex items-center gap-1.5 transition-all hover:gap-2"
                        >
                          원문 보기 <ExternalLink className="w-2.5 h-2.5" />
                        </a>
                      ) : (
                        <span className="text-[9px] uppercase tracking-[0.2em] font-sans text-white/30 flex items-center gap-1.5">
                          원문 없음
                        </span>
                      )}
                    </div>
                  </motion.div>
                ))}
              </div>
            </motion.div>
          )}

          {/* STEP 2: RELATED ARTICLES */}
          {step === 2 && selectedPR && (
            <motion.div
              key="step-2"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20, transition: { duration: 0.3 } }}
              transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
              className="space-y-4"
            >
              <div className="border-l-[3px] border-white/20 pl-3 py-1.5 bg-white/[0.02] p-2 rounded-r-md">
                <div className="text-[9px] font-sans uppercase tracking-[0.2em] text-accent mb-2 flex items-center gap-2">타겟 소스 (보도자료) <SourceLogo source={selectedPR.source} /></div>
                <h3 className="text-base sm:text-lg font-sans font-bold text-ink tracking-tight leading-snug">{selectedPR.title}</h3>
              </div>

              <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3 pb-2 border-b border-white/10 mt-6">
                <h3 className="text-xl sm:text-2xl font-serif tracking-widest uppercase font-bold text-white/90">관련 기사 선택</h3>
                <div className="relative w-full sm:w-60 group">
                  <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-accent group-focus-within:text-ink transition-colors" />
                  <input type="text" placeholder="기사 검색..." className="w-full bg-white/[0.02] border border-white/10 text-ink text-xs pl-9 pr-3 py-2 outline-none focus:border-white/40 focus:bg-white/[0.05] transition-all placeholder:text-white/20 rounded-sm" />
                </div>
              </div>

              <div className="space-y-2 pb-20">
                {isLoadingRelated && (
                  <div className="text-center py-10 text-[11px] font-sans uppercase tracking-[0.2em] text-white/40">
                    관련 기사 검색 중...
                  </div>
                )}
                {!isLoadingRelated && relatedArticles.length === 0 && (
                  <div className="text-center py-10 text-[11px] font-sans uppercase tracking-[0.2em] text-white/40">
                    관련 기사가 없습니다
                  </div>
                )}
                {!isLoadingRelated && relatedArticles.map((article, idx) => {
                  const isSelected = selectedArticles.some(a => a.id === article.id);
                  return (
                    <motion.div
                      key={article.id}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ duration: 0.3, delay: idx * 0.05 }}
                      onClick={() => toggleArticle(article)}
                      className={`group relative border transition-all duration-300 p-3 sm:px-4 flex items-center gap-3 cursor-pointer overflow-hidden rounded-[2px]
                        ${isSelected ? 'border-white/50 bg-white/[0.06] shadow-[0_0_15px_rgba(255,255,255,0.05)]' : 'border-white/10 bg-white/[0.015] hover:border-white/30 hover:bg-white/[0.03]'}`}
                    >
                      {/* Subtly glow when selected */}
                      {isSelected && <div className="absolute inset-0 bg-gradient-to-r from-white/10 to-transparent opacity-50" />}
                      
                      <div className={`flex-none w-4 h-4 border flex items-center justify-center transition-all duration-300 rounded-[2px] ${isSelected ? 'border-ink bg-ink text-bg scale-110 shadow-[0_0_10px_rgba(255,255,255,0.3)]' : 'border-white/30 group-hover:border-white/60'}`}>
                        {isSelected && <motion.span initial={{scale:0}} animate={{scale:1}} className="text-[10px] font-bold">✓</motion.span>}
                      </div>
                      <div className="flex-1 py-0.5">
                        <div className="flex items-center gap-2.5 mb-1.5">
                          <SourceLogo source={article.source} />
                          <span className="text-[9px] font-sans uppercase tracking-[0.2em] text-accent/60">{article.date}</span>
                        </div>
                        <h4 className={`text-[15px] sm:text-[16px] font-sans font-medium tracking-tight transition-colors ${isSelected ? 'text-white' : 'text-white/70 group-hover:text-white/90'}`}>{article.title}</h4>
                      </div>
                      <div className="hidden sm:flex text-[9px] font-sans uppercase tracking-[0.2em] text-accent hover:text-ink items-center gap-1.5 transition-all hover:gap-2 opacity-40 group-hover:opacity-100 z-10">
                        원문 <ExternalLink className="w-2.5 h-2.5" />
                      </div>
                    </motion.div>
                  )
                })}
              </div>

              {/* Sticky bottom bar for selecting articles */}
              <motion.div 
                initial={{ y: 50, opacity: 0 }}
                animate={{ y: 0, opacity: 1 }}
                transition={{ duration: 0.4, delay: 0.2 }}
                className="fixed bottom-0 left-0 w-full p-4 border-t border-white/10 bg-bg/90 backdrop-blur-md z-40 flex justify-center sm:justify-end"
              >
                <div className="max-w-6xl w-full flex justify-end gap-4 items-center">
                   <div className="text-[10px] font-sans text-accent tracking-widest hidden sm:block">
                     {selectedArticles.length}개의 기사 선택됨
                   </div>
                  <button
                    onClick={() => goToStep(3)}
                    className="px-6 py-3 bg-white text-black text-[10px] font-sans uppercase tracking-[0.2em] font-bold hover:shadow-[0_0_15px_rgba(255,255,255,0.4)] transition-all duration-300 flex items-center gap-2 group rounded-sm"
                  >
                    {selectedArticles.length === 0 ? '관련 기사 없이 바로 생성' : '생성 설정 단계로'} <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-1 transition-transform" />
                  </button>
                </div>
              </motion.div>
            </motion.div>
          )}

          {/* STEP 3: GENERATION SETTINGS */}
          {step === 3 && selectedPR && (
            <motion.div
              key="step-3"
              initial={{ opacity: 0, scale: 0.98 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 1.02, transition: { duration: 0.3 } }}
              transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
              className="max-w-3xl mx-auto space-y-6 py-4 sm:py-8 text-center relative"
            >
              <div className="space-y-3">
                <h3 className="text-xl sm:text-2xl font-serif tracking-[0.1em] text-white overflow-hidden font-bold">
                  <motion.span 
                    initial={{ y: "100%" }} 
                    animate={{ y: 0 }} 
                    transition={{ duration: 0.6, ease: "easeOut" }} 
                    className="block"
                  >
                    AI 기사 생성 전 검토
                  </motion.span>
                </h3>
                <motion.p 
                  initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.3, duration: 0.8 }}
                  className="text-accent text-[12px] md:text-[13px] font-light tracking-wide font-sans max-w-xl mx-auto"
                >
                  선택된 소스 데이터를 바탕으로 정제된 AI 기사 생성을 시작하시겠습니까?
                </motion.p>
              </div>

              <motion.div 
                initial={{ opacity: 0, y: 15 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2, duration: 0.6 }}
                className="border border-white/10 p-5 sm:p-6 text-left bg-gradient-to-b from-white/[0.04] to-transparent space-y-5 relative overflow-hidden backdrop-blur-sm shadow-[0_0_40px_rgba(0,0,0,0.3)] rounded-sm"
              >
                <div className="absolute top-0 right-0 p-2 border-b border-l border-white/10 text-[8px] font-sans uppercase tracking-[0.4em] text-accent flex items-center gap-1.5 bg-white/[0.02]">
                  <span className="w-1.5 h-1.5 bg-green-500 rounded-full animate-pulse shadow-[0_0_8px_rgba(34,197,94,0.6)]" /> Ready
                </div>
                
                <div className="space-y-2.5 relative z-10 pt-2">
                  <div className="text-[10px] tracking-[0.2em] font-sans text-accent flex items-center gap-2">
                     메인 타겟 소스
                  </div>
                  <div className="flex items-center gap-3 pl-3 border-l-[3px] border-white/30 py-1">
                     <SourceLogo source={selectedPR.source} />
                     <h4 className="text-sm sm:text-base font-sans font-bold text-white tracking-tight">{selectedPR.title}</h4>
                  </div>
                </div>

                <div className="space-y-3 relative z-10 pt-3 border-t border-white/10">
                  <div className="text-[10px] tracking-[0.2em] font-sans text-accent flex items-center gap-2">
                     참조(병합) 소스 <span className="text-white/40 ml-1">[{selectedArticles.length}개]</span>
                  </div>
                  <div className="pl-3 border-l-[3px] border-white/10 space-y-2 py-1">
                    {selectedArticles.map((article, idx) => (
                      <motion.div 
                        initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: 0.3 + idx * 0.1 }}
                        key={article.id} className="text-[13px] font-sans text-white/70 flex flex-wrap items-start sm:items-center gap-2 group/ref"
                      >
                        <span className="text-[10px] text-accent/50 font-sans mt-0.5 sm:mt-0 font-bold">[{idx + 1}]</span> 
                        <SourceLogo source={article.source} />
                        <span className="group-hover/ref:text-white transition-colors line-clamp-1 flex-1">{article.title}</span> 
                      </motion.div>
                    ))}
                  </div>
                </div>
              </motion.div>

              <motion.div 
                initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ delay: 0.6 }}
                className="flex justify-center pt-4"
              >
                <button 
                  onClick={handleGenerate}
                  disabled={isGenerating}
                  className="relative group overflow-hidden border border-white px-10 py-4 bg-white/5 hover:bg-white/10 transition-all duration-300 hover:-translate-y-1 block animate-[pulse_2s_ease-in-out_infinite] shadow-[0_0_20px_rgba(255,255,255,0.4)] hover:shadow-[0_0_40px_rgba(255,255,255,0.6)] rounded-sm"
                >
                  <motion.div
                    animate={{ opacity: [0, 0.4, 0] }}
                    transition={{ duration: 1.5, repeat: Infinity, ease: 'easeInOut' }}
                    className="absolute inset-0 bg-white"
                  />
                  <span className={`relative z-10 text-[12px] font-sans tracking-[0.2em] text-white font-black flex items-center gap-3 transition-opacity ${isGenerating ? 'opacity-0' : 'opacity-100'}`}>
                    AI 기사 생성 시작 <ArrowRight className="w-4 h-4 group-hover:translate-x-1.5 transition-transform" />
                  </span>
                  
                  {isGenerating && (
                    <span className="absolute inset-0 flex items-center justify-center z-20 text-[12px] font-sans tracking-[0.2em] text-white font-bold bg-black/60 backdrop-blur-md">
                      <RefreshCcw className="w-3.5 h-3.5 animate-spin mr-2" /> 생성 중...
                    </span>
                  )}
                  
                  <div className={`absolute bottom-0 left-0 h-[2px] bg-gradient-to-r from-transparent via-white to-transparent transition-all duration-[2.5s] ease-linear opacity-90 ${isGenerating ? 'w-[200%] -translate-x-1/2 animate-pulse' : 'w-0 group-hover:w-[100%] duration-500'}`} />
                </button>
              </motion.div>
            </motion.div>
          )}

          {/* STEP 4: AI EDITOR */}
          {step === 4 && selectedPR && (
            <motion.div
              key="step-4"
              initial={{ opacity: 0, filter: "blur(10px)", scale: 0.98 }}
              animate={{ opacity: 1, filter: "blur(0px)", scale: 1 }}
              transition={{ duration: 0.6, ease: "easeOut" }}
              className="grid grid-cols-1 lg:grid-cols-4 gap-6"
            >
              {/* Main Editor */}
              <div className="lg:col-span-3 border border-white/10 bg-[#0a0a0a] p-4 sm:p-8 min-h-[60vh] shadow-[0_0_40px_rgba(0,0,0,0.5)] relative rounded-sm">
                {/* Editor Top Bar */}
                <div className="mb-5 border-b border-white/10 pb-3 flex justify-between items-end">
                  <div className="text-[9px] tracking-[0.3em] text-accent font-sans flex items-center gap-2">
                    <span className="w-1.5 h-1.5 bg-accent rounded-full animate-pulse" /> 에디토리얼 콘솔
                  </div>
                  <div className="flex gap-3 items-center">
                    <button className="text-[9px] tracking-[0.2em] font-sans px-3 py-1.5 transition-all font-bold rounded-sm bg-white/10 text-white hover:bg-white hover:text-black border border-white/20 hover:border-transparent flex items-center gap-1.5">
                      <RefreshCcw className="w-3 h-3" /> 기사 재작성
                    </button>
                    <button 
                      onClick={() => setIsEditing(!isEditing)}
                      className={`text-[9px] tracking-[0.2em] font-sans px-3 py-1.5 transition-all font-bold rounded-sm ${isEditing ? 'bg-white text-black shadow-[0_0_10px_rgba(255,255,255,0.4)]' : 'bg-[#1a1a1a] text-white hover:bg-white/10 border border-white/20'}`}
                    >
                      {isEditing ? '편집 취소' : '편집 활성화'}
                    </button>
                    <div className="text-[8px] uppercase tracking-[0.2em] text-accent font-mono border border-white/10 px-2 py-1 bg-white/5 hidden sm:block rounded-sm">OOTHREE / V 1.0</div>
                  </div>
                </div>

                <div className="space-y-4">
                  <motion.div initial={{opacity:0, y:-10}} animate={{opacity:1,y:0}} transition={{delay:0.2}} className="space-y-1.5 group relative">
                    {isEditing && (
                      <label className="text-[9px] uppercase tracking-[0.2em] text-accent font-sans font-medium flex items-center gap-1.5 px-2">
                         기사 제목
                      </label>
                    )}
                    <input
                      type="text"
                      value={generated?.title ?? ''}
                      readOnly={!isEditing}
                      onChange={(e) => setGenerated((g) => g ? { ...g, title: e.target.value } : g)}
                      className={`w-full bg-transparent text-xl sm:text-2xl font-sans font-bold tracking-tight text-white outline-none transition-all px-2 ${isEditing ? 'border-b border-white/30 hover:border-white focus:border-white focus:bg-white/[0.03] py-2 rounded-sm' : 'border-transparent py-1'}`}
                    />
                  </motion.div>

                  <motion.div initial={{opacity:0, y:-10}} animate={{opacity:1,y:0}} transition={{delay:0.4}} className="space-y-1.5 group relative">
                    {isEditing && (
                      <label className="text-[9px] uppercase tracking-[0.2em] text-accent font-sans font-medium flex items-center gap-1.5 px-2 mt-2">
                         리드 문단
                      </label>
                    )}
                    <textarea
                      value={generated?.lead ?? ''}
                      readOnly={!isEditing}
                      onChange={(e) => setGenerated((g) => g ? { ...g, lead: e.target.value } : g)}
                      className={`w-full bg-transparent text-base sm:text-[17px] font-sans font-medium text-orange-400 leading-relaxed outline-none transition-all resize-none min-h-[90px] px-2 ${isEditing ? 'border-l-2 border-white/60 focus:bg-white/[0.03] py-2 rounded-sm' : 'border-transparent py-1'}`}
                    />
                  </motion.div>

                  <motion.div initial={{opacity:0, y:-10}} animate={{opacity:1,y:0}} transition={{delay:0.6}} className="space-y-1.5 group">
                    {isEditing && (
                      <label className="text-[9px] uppercase tracking-[0.2em] text-accent font-sans font-medium flex justify-between items-center px-2 mt-2">
                        <span>본문 내용</span>
                      </label>
                    )}
                    {isEditing ? (
                      <textarea
                        value={generated?.body ?? ''}
                        onChange={(e) => setGenerated((g) => g ? { ...g, body: e.target.value } : g)}
                        className="w-full bg-transparent text-[14px] sm:text-[15px] font-sans font-normal text-white/80 leading-[1.8] outline-none transition-all border border-white/20 focus:bg-white/[0.02] p-3 rounded-sm min-h-[300px] resize-y"
                      />
                    ) : (
                      <BodyWithCitations
                        body={generated?.body ?? ''}
                        citations={generated?.citations ?? {}}
                      />
                    )}
                  </motion.div>
                </div>

                {/* Related Articles below content */}
                {(selectedArticles.length > 0) && (
                  <motion.div initial={{opacity:0, y:-10}} animate={{opacity:1,y:0}} transition={{delay:0.7}} className="mt-12 border-t border-white/10 pt-6 px-2">
                    <h4 className="text-[11px] uppercase tracking-[0.2em] text-accent font-sans mb-4 flex items-center gap-2">
                      관련 기사
                    </h4>
                    <div className="space-y-3">
                      {selectedArticles.map((article) => (
                        <a
                          key={article.id}
                          href={article.detail_url || '#'}
                          target={article.detail_url ? '_blank' : undefined}
                          rel={article.detail_url ? 'noreferrer' : undefined}
                          className="block group/link"
                        >
                           <div className="flex items-center gap-3">
                             <div className="w-1.5 h-1.5 rounded-full bg-white/20 group-hover/link:bg-white/60 transition-colors" />
                             <span className="text-[13px] sm:text-[14px] text-white/70 group-hover/link:text-white transition-colors tracking-tight">
                               {article.title} <span className="text-white/30 text-[11px] ml-2 font-mono">{article.source}</span>
                             </span>
                           </div>
                        </a>
                      ))}
                    </div>
                  </motion.div>
                )}
              </div>

              {/* Sidebar */}
              <motion.div initial={{opacity:0, x:20}} animate={{opacity:1,x:0}} transition={{delay:0.5}} className="space-y-4">
                <div className="border border-white/10 bg-white/[0.02] p-5 space-y-3 backdrop-blur-md rounded-sm">
                  <h4 className="text-[10px] tracking-[0.2em] text-accent border-b border-white/10 font-sans pb-3 mb-4 flex items-center gap-2">
                    <Download className="w-3 h-3" /> 내보내기
                  </h4>
                  
                  <button className="w-full flex items-center justify-between text-[10px] uppercase tracking-[0.1em] font-sans text-ink hover:text-black border border-white/20 p-4 hover:bg-white transition-all duration-300 group rounded-sm">
                    Word 문서 (.docx) <ArrowRight className="w-3 h-3 group-hover:translate-x-1 transition-transform" />
                  </button>
                  <button className="w-full flex items-center justify-between text-[10px] uppercase tracking-[0.1em] font-sans text-ink hover:text-black border border-white/20 p-4 hover:bg-white transition-all duration-300 group rounded-sm">
                    PDF 문서 (.pdf) <ArrowRight className="w-3 h-3 group-hover:translate-x-1 transition-transform" />
                  </button>
                  <button className="w-full flex items-center justify-between text-[10px] uppercase tracking-[0.1em] font-sans text-accent hover:text-ink hover:border-white/40 border border-transparent p-4 transition-all duration-300 mt-1 hover:bg-white/5 cursor-pointer rounded-sm">
                    클립보드에 복사 <FileText className="w-3 h-3" />
                  </button>
                </div>


              </motion.div>
            </motion.div>
          )}

        </AnimatePresence>
      </div>
    </section>
  );
}
