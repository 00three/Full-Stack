import React, { useState, useEffect, useRef, useMemo } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import confetti from 'canvas-confetti';
import {
  Search, RefreshCcw, ExternalLink,
  ChevronRight, ArrowRight, Download,
  Info, CheckCircle2, X, Image as ImageIcon, Plus, Trash2
} from 'lucide-react';
import {
  API_BASE,
  fetchPressReleases,
  fetchRelatedArticles,
  fetchLLMModels,
  generateArticleStream,
  type PressRelease,
  type RelatedArticle,
  type GeneratedArticle,
  type LLMModelOption,
  type ArticleStyle,
  type ArticleTone,
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
    },
    '국민일보': {
      src: '/logos/kukminilbo.png',
      className: 'h-4 sm:h-5 max-w-[96px] sm:max-w-[112px] w-auto object-contain bg-white px-1.5 py-0.5 rounded-[1px]',
      fallback: 'bg-white text-black px-1.5 py-0.5 font-bold text-[9px] rounded-sm'
    },
    '중앙일보': {
      src: '/logos/joongangilbo.png',
      className: 'h-4 sm:h-5 max-w-[96px] sm:max-w-[112px] w-auto object-contain bg-white px-1.5 py-0.5 rounded-[1px]',
      fallback: 'bg-white text-black px-1.5 py-0.5 font-bold text-[9px] rounded-sm'
    },
    '연합뉴스': {
      src: '/logos/yonhapnews.jpg',
      className: 'h-4 sm:h-5 max-w-[112px] sm:max-w-[130px] w-auto object-contain bg-white px-1.5 py-0.5 rounded-[1px]',
      fallback: 'bg-white text-black px-1.5 py-0.5 font-bold text-[9px] rounded-sm'
    },
    '뉴스1': {
      src: '/logos/news1.png',
      className: 'h-4 sm:h-5 max-w-[84px] sm:max-w-[96px] w-auto object-contain bg-white px-1.5 py-0.5 rounded-[1px]',
      fallback: 'bg-white text-black px-1.5 py-0.5 font-bold text-[9px] rounded-sm'
    },
    '파이낸셜뉴스': {
      src: '/logos/financialnews.png',
      className: 'h-4 sm:h-5 max-w-[118px] sm:max-w-[136px] w-auto object-contain bg-white px-1.5 py-0.5 rounded-[1px]',
      fallback: 'bg-[#0b74b7] text-white px-1.5 py-0.5 font-bold text-[9px] rounded-sm'
    },
    '뉴시스': {
      src: '/logos/newsis.jpg',
      className: 'h-4 sm:h-5 max-w-[104px] sm:max-w-[120px] w-auto object-contain bg-white px-1.5 py-0.5 rounded-[1px]',
      fallback: 'bg-white text-[#d90429] px-1.5 py-0.5 font-bold text-[9px] rounded-sm'
    },
    '매일경제': {
      src: '/logos/maeilbiz.png',
      className: 'h-4 sm:h-5 max-w-[112px] sm:max-w-[132px] w-auto object-contain bg-white px-1.5 py-0.5 rounded-[1px]',
      fallback: 'bg-white text-black px-1.5 py-0.5 font-bold text-[9px] rounded-sm'
    },
    '창업일보': {
      src: '/logos/startupilbo.png',
      className: 'h-4 sm:h-5 max-w-[96px] sm:max-w-[112px] w-auto object-contain bg-white px-1.5 py-0.5 rounded-[1px]',
      fallback: 'bg-white text-black px-1.5 py-0.5 font-bold text-[9px] rounded-sm'
    },
    '글로벌이코노믹': {
      src: '/logos/global-economic.png',
      className: 'h-4 sm:h-5 max-w-[118px] sm:max-w-[138px] w-auto object-contain bg-white px-1.5 py-0.5 rounded-[1px]',
      fallback: 'bg-white text-[#d4145a] px-1.5 py-0.5 font-bold text-[9px] rounded-sm'
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

const seededRandom = (seed: number) => {
  const x = Math.sin(seed) * 10000;
  return x - Math.floor(x);
};

const AmbientButterflies = () => {
  const butterflies = useMemo(() => Array.from({ length: 14 }).map((_, i) => {
    const zones = ['left', 'right', 'top', 'bottom'];
    const zone = zones[i % 4];
    
    const xPoints: number[] = [];
    const yPoints: number[] = [];
    const rPoints: number[] = [];
    let randomStep = i * 23 + 1;
    const nextRandom = () => seededRandom(randomStep++);
    let currentR = nextRandom() * 360;

    for(let j=0; j<6; j++) {
      if (zone === 'left') {
        xPoints.push(nextRandom() * 25 - 5); // -5 to 20vw
        yPoints.push(nextRandom() * 110 - 5);
      } else if (zone === 'right') {
        xPoints.push(75 + nextRandom() * 30); // 75 to 105vw
        yPoints.push(nextRandom() * 110 - 5);
      } else if (zone === 'top') {
        xPoints.push(nextRandom() * 110 - 5);
        yPoints.push(nextRandom() * 20 - 5); // -5 to 15vh
      } else { // bottom
        xPoints.push(nextRandom() * 110 - 5);
        yPoints.push(85 + nextRandom() * 20); // 85 to 105vh
      }
      rPoints.push(currentR);
      currentR += (nextRandom() * 180 - 90); // Drift rotation slowly
    }
    
    // Link back to start for smooth endless loop
    xPoints.push(xPoints[0]);
    yPoints.push(yPoints[0]);
    rPoints.push(currentR);

    const duration = nextRandom() * 100 + 80; // 80-180s very slow, random path
    
    return {
      id: i,
      xPoints,
      yPoints,
      rPoints,
      duration,
      delay: -(nextRandom() * duration), // Start scattered along the path
      scale: nextRandom() * 0.4 + 0.3,
      flutterDuration: nextRandom() * 0.5 + 0.4, // Slow, graceful flap
      bobDuration: nextRandom() * 6 + 6,
      waverDuration: nextRandom() * 5 + 5,
    };
  }), []);

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
              y: { duration: b.bobDuration, repeat: Infinity, ease: "easeInOut" },
              rotate: { duration: b.waverDuration, repeat: Infinity, ease: "easeInOut" }
            }}
          >
            <Butterfly className="w-20 h-20 drop-shadow-[0_0_12px_rgba(255,255,255,0.5)] text-accent/70" />
          </motion.div>
        </motion.div>
      ))}
    </div>
  );
};

const formatUpdatedAt = (date: Date) =>
  date.toLocaleString('ko-KR', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });

type GenerationStep = {
  stage: string;
  message: string;
};

type ImagePlacement = 'after-lead' | `after-${number}`;

type ArticleImageAsset = {
  id: string;
  url: string;
  source: string;
  title: string;
  date?: string;
  sourceLabel: string;
};

type InsertedArticleImage = ArticleImageAsset & {
  insertId: string;
  placement: ImagePlacement;
  caption: string;
};

type ExportImageData = InsertedArticleImage & {
  data: Uint8Array;
  type: 'jpg' | 'png' | 'gif' | 'bmp';
  width: number;
  height: number;
};

type SourceColumnConfig = {
  key: 'kcc' | 'union' | 'mbc' | 'nsp';
  label: string;
  sourceForLogo: string;
  aliases: string[];
};

const SOURCE_COLUMNS: SourceColumnConfig[] = [
  {
    key: 'kcc',
    label: '방송통신위원회',
    sourceForLogo: '방송통신위원회',
    aliases: ['방송통신위원회', 'KCC'],
  },
  {
    key: 'union',
    label: '언론노조',
    sourceForLogo: '언론노조',
    aliases: ['언론노조', 'NODONG'],
  },
  {
    key: 'mbc',
    label: 'MBC',
    sourceForLogo: 'MBC',
    aliases: ['MBC'],
  },
  {
    key: 'nsp',
    label: '국회도서관',
    sourceForLogo: '국회도서관',
    aliases: ['국회도서관', 'NSP', 'NAIL'],
  },
];

const resolveSourceColumnKey = (source: string): SourceColumnConfig['key'] => {
  const normalized = source.trim().toLowerCase();
  const matched = SOURCE_COLUMNS.find((column) =>
    column.aliases.some((alias) => normalized.includes(alias.toLowerCase())),
  );
  return matched?.key ?? 'nsp';
};

const GENERATION_FLOW: GenerationStep[] = [
  { stage: 'extracting', message: '핵심 사실을 정리하는 중입니다.' },
  { stage: 'drafting', message: '기사 초안 생성을 요청했습니다.' },
  { stage: 'streaming', message: '초안이 실시간으로 내려오고 있습니다.' },
  { stage: 'assembling', message: '생성문을 정리하는 중입니다.' },
  { stage: 'saving', message: '생성 결과를 DB에 저장하는 중입니다.' },
  { stage: 'complete', message: '생성 완료. 결과 화면으로 이동합니다.' },
];
const VISIBLE_GENERATION_STAGES = new Set(GENERATION_FLOW.map((item) => item.stage));

const ARTICLE_TONE_OPTIONS: Array<{ value: ArticleTone; label: string; description: string }> = [
  { value: 'default', label: '기본값', description: '기본 스타일과 말투' },
  { value: 'professional', label: '전문적', description: '정제되어 있고 정확함' },
  { value: 'friendly', label: '친근함', description: '따뜻하고 수다스러움' },
  { value: 'direct', label: '솔직함', description: '직설적이면서도 격려함' },
  { value: 'distinctive', label: '독특함', description: '유쾌하고 상상력이 풍부함' },
  { value: 'efficient', label: '효율적', description: '간결하고 꾸밈없음' },
  { value: 'critical', label: '냉소적', description: '비판적이고 거리를 둠' },
  { value: 'mz', label: 'MZ 친화', description: '밈·반말·이모지 허용' },
];

export default function NewsDashboard() {
  const [step, setStep] = useState<0 | 1 | 2 | 3 | 4>(0);
  const [reporterInfo, setReporterInfo] = useState({ media: '', name: '' });
  const [pressReleases, setPressReleases] = useState<PressRelease[]>([]);
  const [isLoadingPRs, setIsLoadingPRs] = useState(true);
  const [prsError, setPrsError] = useState<string | null>(null);
  const [pressQuery, setPressQuery] = useState('');
  const [selectedSourceFilter, setSelectedSourceFilter] = useState<SourceColumnConfig['key'] | 'all'>('all');
  const [selectedPR, setSelectedPR] = useState<PressRelease | null>(null);
  const [relatedArticles, setRelatedArticles] = useState<RelatedArticle[]>([]);
  const [relatedQuery, setRelatedQuery] = useState('');
  const [isLoadingRelated, setIsLoadingRelated] = useState(false);
  const [selectedArticles, setSelectedArticles] = useState<RelatedArticle[]>([]);
  const [isGenerating, setIsGenerating] = useState(false);
  const [generated, setGenerated] = useState<GeneratedArticle | null>(null);
  const [generateError, setGenerateError] = useState<string | null>(null);
  const [generationStatus, setGenerationStatus] = useState('');
  const [generationPreview, setGenerationPreview] = useState('');
  const [generationSteps, setGenerationSteps] = useState<GenerationStep[]>([]);
  const [llmModels, setLlmModels] = useState<LLMModelOption[]>([
    {
      key: 'claude-sonnet-4-6',
      label: 'Claude Sonnet 4.6',
      provider: 'bedrock',
      family: 'Claude',
    },
  ]);
  const [selectedModelKey, setSelectedModelKey] = useState('claude-sonnet-4-6');
  const [articleStyle, setArticleStyle] = useState<ArticleStyle>('default');
  const [articleTone, setArticleTone] = useState<ArticleTone>('default');
  const [llmModelsError, setLlmModelsError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<string>('');
  const [isEditing, setIsEditing] = useState(false);
  const [detailPressRelease, setDetailPressRelease] = useState<PressRelease | null>(null);
  const [imagePlacement, setImagePlacement] = useState<ImagePlacement>('after-lead');
  const [insertedImages, setInsertedImages] = useState<InsertedArticleImage[]>([]);
  const [isExportingWord, setIsExportingWord] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);
  const stepRefs = useRef<(HTMLSpanElement | null)[]>([]);
  const generationPreviewRef = useRef<HTMLPreElement | null>(null);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setLastUpdated(formatUpdatedAt(new Date()));
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  useEffect(() => {
    let cancelled = false;
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

  useEffect(() => {
    let cancelled = false;
    fetchLLMModels()
      .then((catalog) => {
        if (cancelled) return;
        setLlmModels(catalog.models);
        setSelectedModelKey(catalog.default_model_key);
        setLlmModelsError(null);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setLlmModelsError(err instanceof Error ? err.message : '모델 목록을 불러오지 못했습니다');
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!generationPreview) return;
    const frame = requestAnimationFrame(() => {
      const el = generationPreviewRef.current;
      if (el) {
        el.scrollTop = el.scrollHeight;
      }
    });
    return () => cancelAnimationFrame(frame);
  }, [generationPreview]);

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
    setRelatedQuery('');
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

  const filteredRelatedArticles = useMemo(() => {
    const query = relatedQuery.trim().toLowerCase();
    if (!query) return relatedArticles;
    return relatedArticles.filter((article) => {
      const haystack = [
        article.title,
        article.source,
        article.date,
        article.document_kind,
      ].join(' ').toLowerCase();
      return haystack.includes(query);
    });
  }, [relatedArticles, relatedQuery]);

  const filteredPressReleases = useMemo(() => {
    const query = pressQuery.trim().toLowerCase();
    return pressReleases.filter((pr) => {
      if (selectedSourceFilter !== 'all' && resolveSourceColumnKey(pr.source) !== selectedSourceFilter) {
        return false;
      }
      if (!query) return true;
      const haystack = [
        pr.title,
        pr.source,
        pr.date,
        pr.summary,
      ].join(' ').toLowerCase();
      return haystack.includes(query);
    });
  }, [pressReleases, pressQuery, selectedSourceFilter]);

  const detailImages = useMemo(() => {
    if (!detailPressRelease) return [];
    const urls = [
      detailPressRelease.thumbnailUrl,
      ...(detailPressRelease.imageUrls ?? []),
    ].filter((url): url is string => !!url);
    return Array.from(new Set(urls));
  }, [detailPressRelease]);

  const generatedBodyParagraphs = useMemo(
    () => (generated?.body ?? '').split(/\n+/).filter((paragraph) => paragraph.trim().length > 0),
    [generated?.body],
  );

  const imageTargets = useMemo(() => {
    const bodyTargets = generatedBodyParagraphs.map((_, idx) => ({
      value: `after-${idx}` as ImagePlacement,
      label: `본문 ${idx + 1}문단 뒤`,
    }));
    return [{ value: 'after-lead' as ImagePlacement, label: '리드 아래' }, ...bodyTargets];
  }, [generatedBodyParagraphs]);

  const availableArticleImages = useMemo<ArticleImageAsset[]>(() => {
    const assets: ArticleImageAsset[] = [];
    const seen = new Set<string>();
    const pushAsset = (
      url: string | undefined,
      source: string,
      title: string,
      sourceLabel: string,
      date?: string,
    ) => {
      if (!url || seen.has(url)) return;
      seen.add(url);
      assets.push({
        id: `${sourceLabel}-${assets.length}`,
        url,
        source,
        title,
        date,
        sourceLabel,
      });
    };

    if (selectedPR) {
      const urls = [selectedPR.thumbnailUrl, ...(selectedPR.imageUrls ?? [])];
      urls.forEach((url) => pushAsset(url, selectedPR.source, selectedPR.title, '메인 보도자료', selectedPR.date));
    }

    selectedArticles.forEach((article, idx) => {
      const urls = [article.thumbnailUrl, ...(article.imageUrls ?? [])];
      urls.forEach((url) => pushAsset(url, article.source, article.title, `관련기사 ${idx + 1}`, article.date));
    });

    return assets;
  }, [selectedPR, selectedArticles]);

  const bodyImageInserts = useMemo(() => {
    const grouped: Record<number, InsertedArticleImage[]> = {};
    insertedImages.forEach((image) => {
      if (image.placement === 'after-lead') return;
      const idx = Number(image.placement.replace('after-', ''));
      if (!Number.isFinite(idx)) return;
      grouped[idx] = [...(grouped[idx] ?? []), image];
    });
    return grouped;
  }, [insertedImages]);

  const leadImages = useMemo(
    () => insertedImages.filter((image) => image.placement === 'after-lead'),
    [insertedImages],
  );

  const handleGenerate = () => {
    if (!selectedPR) return;
    let sawToken = false;
    const pushGenerationStep = (stage: string, message: string) => {
      if (!VISIBLE_GENERATION_STAGES.has(stage)) return;
      setGenerationSteps((prev) => {
        const nextStep = { stage, message };
        const last = prev[prev.length - 1];
        if (last?.stage === stage) {
          return [...prev.slice(0, -1), nextStep];
        }
        return [...prev, nextStep].slice(-8);
      });
    };

    setIsGenerating(true);
    setGenerateError(null);
    setGenerationStatus('핵심 사실을 정리하는 중입니다.');
    setGenerationSteps([{ stage: 'extracting', message: '핵심 사실을 정리하는 중입니다.' }]);
    setGenerationPreview('');
    setInsertedImages([]);
    generateArticleStream(
      [selectedPR.id],
      selectedArticles.map((a) => a.id),
      reporterInfo.name,
      selectedModelKey,
      articleStyle,
      articleTone,
      (event) => {
        if (event.type === 'stage') {
          setGenerationStatus(event.message);
          pushGenerationStep(event.stage, event.message);
        }
        if (event.type === 'token') {
          if (!sawToken) {
            sawToken = true;
            setGenerationStatus('초안이 실시간으로 내려오고 있습니다.');
            pushGenerationStep('streaming', '초안이 실시간으로 내려오고 있습니다.');
          }
          setGenerationPreview((prev) => prev + event.delta);
        }
        if (event.type === 'complete') {
          setGenerationStatus('생성 완료. 결과 화면으로 이동합니다.');
          pushGenerationStep('complete', '생성 완료. 결과 화면으로 이동합니다.');
        }
      },
    )
      .then(async (article) => {
        setGenerated(article);
        await new Promise((resolve) => setTimeout(resolve, 900));
        setStep(4);
      })
      .catch((err: unknown) => {
        setGenerateError(err instanceof Error ? err.message : '기사 생성에 실패했습니다');
      })
      .finally(() => setIsGenerating(false));
  };

  const insertArticleImage = (asset: ArticleImageAsset) => {
    const safePlacement = imageTargets.some((target) => target.value === imagePlacement)
      ? imagePlacement
      : 'after-lead';
    setInsertedImages((prev) => [
      ...prev,
      {
        ...asset,
        insertId: `${asset.id}-${Date.now()}-${prev.length}`,
        placement: safePlacement,
        caption: `${asset.sourceLabel} · ${asset.source}`,
      },
    ]);
  };

  const removeArticleImage = (insertId: string) => {
    setInsertedImages((prev) => prev.filter((image) => image.insertId !== insertId));
  };

  const renderInsertedImage = (image: InsertedArticleImage) => (
    <figure
      key={image.insertId}
      className="group/image relative overflow-hidden rounded-sm border border-white/10 bg-white/[0.025] p-2"
    >
      {isEditing && (
        <button
          type="button"
          onClick={() => removeArticleImage(image.insertId)}
          className="absolute right-3 top-3 z-10 flex h-7 w-7 items-center justify-center rounded-sm border border-white/15 bg-black/70 text-white/70 opacity-0 backdrop-blur transition-all hover:border-white/40 hover:text-white group-hover/image:opacity-100"
          aria-label="이미지 삭제"
        >
          <Trash2 className="h-3.5 w-3.5" />
        </button>
      )}
      <img
        src={image.url}
        alt={image.title}
        className="max-h-[360px] w-full rounded-[2px] object-contain"
        loading="lazy"
      />
      <figcaption className="mt-2 flex flex-wrap items-center gap-2 px-1 text-[10px] font-sans text-white/45">
        <span className="uppercase tracking-[0.16em] text-accent/70">{image.caption}</span>
        <span className="line-clamp-1">{image.title}</span>
      </figcaption>
    </figure>
  );

  const imageTypeFromBlob = (blob: Blob, url: string): ExportImageData['type'] | null => {
    const mime = blob.type.toLowerCase();
    if (mime.includes('png')) return 'png';
    if (mime.includes('gif')) return 'gif';
    if (mime.includes('bmp')) return 'bmp';
    if (mime.includes('jpeg') || mime.includes('jpg')) return 'jpg';
    const lowerUrl = url.toLowerCase();
    if (lowerUrl.endsWith('.png')) return 'png';
    if (lowerUrl.endsWith('.gif')) return 'gif';
    if (lowerUrl.endsWith('.bmp')) return 'bmp';
    if (lowerUrl.endsWith('.jpg') || lowerUrl.endsWith('.jpeg')) return 'jpg';
    return null;
  };

  const stripCitationMarkers = (text: string) =>
    text
      .replace(/\s*\[\d+\]/g, '')
      .replace(/[ \t]{2,}/g, ' ')
      .trim();

  const convertImageBlobToPng = (blob: Blob): Promise<Blob | null> =>
    new Promise((resolve) => {
      const objectUrl = URL.createObjectURL(blob);
      const img = new window.Image();
      img.onload = () => {
        const canvas = document.createElement('canvas');
        canvas.width = Math.max(1, img.naturalWidth || img.width);
        canvas.height = Math.max(1, img.naturalHeight || img.height);
        const ctx = canvas.getContext('2d');
        if (!ctx) {
          URL.revokeObjectURL(objectUrl);
          resolve(null);
          return;
        }
        ctx.drawImage(img, 0, 0);
        canvas.toBlob((pngBlob) => {
          URL.revokeObjectURL(objectUrl);
          resolve(pngBlob);
        }, 'image/png');
      };
      img.onerror = () => {
        URL.revokeObjectURL(objectUrl);
        resolve(null);
      };
      img.src = objectUrl;
    });

  const normalizeImageBlobForWord = async (
    blob: Blob,
    url: string,
  ): Promise<{ blob: Blob; type: ExportImageData['type'] } | null> => {
    const nativeType = imageTypeFromBlob(blob, url);
    if (nativeType) return { blob, type: nativeType };

    const converted = await convertImageBlobToPng(blob);
    if (!converted) return null;
    return { blob: converted, type: 'png' };
  };

  const getScaledImageSize = (blob: Blob): Promise<{ width: number; height: number }> =>
    new Promise((resolve) => {
      const objectUrl = URL.createObjectURL(blob);
      const img = new window.Image();
      img.onload = () => {
        const maxWidth = 560;
        const maxHeight = 360;
        const ratio = Math.min(maxWidth / img.naturalWidth, maxHeight / img.naturalHeight, 1);
        URL.revokeObjectURL(objectUrl);
        resolve({
          width: Math.max(1, Math.round(img.naturalWidth * ratio)),
          height: Math.max(1, Math.round(img.naturalHeight * ratio)),
        });
      };
      img.onerror = () => {
        URL.revokeObjectURL(objectUrl);
        resolve({ width: 520, height: 300 });
      };
      img.src = objectUrl;
    });

  const fetchExportImage = async (image: InsertedArticleImage): Promise<ExportImageData | null> => {
    const apiBase = API_BASE.replace(/\/$/, '');
    const proxyUrl = `${apiBase}/assets/image-proxy?url=${encodeURIComponent(image.url)}`;
    const candidateUrls = image.url.startsWith('data:image/') ? [image.url] : [proxyUrl, image.url];

    for (const url of candidateUrls) {
      try {
        const response = await fetch(url);
        if (!response.ok) continue;
        const fetchedBlob = await response.blob();
        const normalized = await normalizeImageBlobForWord(fetchedBlob, image.url);
        if (!normalized) continue;
        const [arrayBuffer, size] = await Promise.all([
          normalized.blob.arrayBuffer(),
          getScaledImageSize(normalized.blob),
        ]);
        return {
          ...image,
          type: normalized.type,
          data: new Uint8Array(arrayBuffer),
          width: size.width,
          height: size.height,
        };
      } catch {
        // Try the next candidate. Remote article images often block direct browser fetches.
      }
    }
    return null;
  };

  const exportArticleToWord = async () => {
    if (!generated) return;
    setIsExportingWord(true);
    setExportError(null);

    try {
      const {
        AlignmentType,
        Document,
        HeadingLevel,
        ImageRun,
        Packer,
        Paragraph,
        TextRun,
      } = await import('docx');

      const exportImages = (await Promise.all(insertedImages.map(fetchExportImage))).filter(
        (image): image is ExportImageData => Boolean(image),
      );
      const exportImagesFor = (placement: ImagePlacement) =>
        exportImages.filter((image) => image.placement === placement);

      const imageParagraphs = (images: ExportImageData[]) =>
        images.flatMap((image) => [
          new Paragraph({
            alignment: AlignmentType.CENTER,
            spacing: { before: 180, after: 80 },
            children: [
              new ImageRun({
                type: image.type,
                data: image.data,
                transformation: { width: image.width, height: image.height },
                altText: {
                  title: image.title,
                  description: image.title,
                  name: image.caption,
                },
              }),
            ],
          }),
          new Paragraph({
            alignment: AlignmentType.CENTER,
            spacing: { after: 220 },
            children: [
              new TextRun({
                text: `${image.caption} · ${image.title}`,
                italics: true,
                color: '666666',
                size: 18,
              }),
            ],
          }),
        ]);

      const bodyParagraphs = (generated.body ?? '')
        .split(/\n+/)
        .map((paragraph) => stripCitationMarkers(paragraph))
        .filter(Boolean);

      const children = [
        new Paragraph({
          text: stripCitationMarkers(generated.title || '제목 없음'),
          heading: HeadingLevel.TITLE,
          spacing: { after: 260 },
        }),
        new Paragraph({
          spacing: { after: 240 },
          children: [
            new TextRun({
              text: stripCitationMarkers(generated.lead || ''),
              bold: true,
              color: 'C55A11',
              size: 28,
            }),
          ],
        }),
        ...imageParagraphs(exportImagesFor('after-lead')),
      ];

      bodyParagraphs.forEach((paragraph, idx) => {
        children.push(
          new Paragraph({
            spacing: { after: 220 },
            children: [
              new TextRun({
                text: paragraph,
                size: 24,
              }),
            ],
          }),
          ...imageParagraphs(exportImagesFor(`after-${idx}` as ImagePlacement)),
        );
      });

      children.push(
        new Paragraph({
          text: '사용한 소스',
          heading: HeadingLevel.HEADING_2,
          spacing: { before: 360, after: 160 },
        }),
        new Paragraph({
          children: [
            new TextRun({
              text: `메인 보도자료: ${selectedPR?.source ?? ''} ${selectedPR?.date ?? ''} - ${selectedPR?.title ?? ''}`,
              size: 20,
            }),
          ],
          spacing: { after: 120 },
        }),
      );

      selectedArticles.forEach((article, idx) => {
        children.push(
          new Paragraph({
            children: [
              new TextRun({
                text: `관련기사 ${idx + 1}: ${article.source} ${article.date} - ${article.title}`,
                size: 20,
              }),
            ],
            spacing: { after: 120 },
          }),
        );
      });

      const doc = new Document({
        sections: [
          {
            properties: {},
            children,
          },
        ],
      });

      const blob = await Packer.toBlob(doc);
      const objectUrl = URL.createObjectURL(blob);
      const link = document.createElement('a');
      const filename = (generated.title || 'generated-article')
        .replace(/[\\/:*?"<>|]/g, ' ')
        .replace(/\s+/g, ' ')
        .trim()
        .slice(0, 80) || 'generated-article';
      link.href = objectUrl;
      link.download = `${filename}.docx`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(objectUrl);

      if (exportImages.length < insertedImages.length) {
        setExportError(`이미지 ${insertedImages.length - exportImages.length}개는 원본 접근 제한으로 제외하고 내보냈습니다.`);
      }
    } catch (err) {
      setExportError(err instanceof Error ? err.message : 'Word 문서 내보내기에 실패했습니다.');
    } finally {
      setIsExportingWord(false);
    }
  };

  return (
    <section className="min-h-screen bg-bg text-ink pt-12 pb-24 px-4 sm:px-6 selection:bg-white/20 relative overflow-hidden">
      {/* Subtle ambient background glow */}
      <div className="absolute top-1/4 left-1/2 -translate-x-1/2 w-[600px] h-[600px] bg-white/[0.015] rounded-full blur-[100px] pointer-events-none" />

      <AmbientButterflies />

      <AnimatePresence>
        {detailPressRelease && (
          <motion.div
            className="fixed inset-0 z-[80] flex items-center justify-center bg-black/75 px-4 py-8 backdrop-blur-sm"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setDetailPressRelease(null)}
          >
            <motion.div
              initial={{ opacity: 0, y: 18, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 10, scale: 0.98 }}
              transition={{ duration: 0.22, ease: 'easeOut' }}
              onClick={(e) => e.stopPropagation()}
              className="relative max-h-[86vh] w-full max-w-3xl overflow-y-auto rounded-sm border border-white/15 bg-[#080808] shadow-[0_30px_120px_rgba(0,0,0,0.85)]"
            >
              <div className="sticky top-0 z-10 flex items-center justify-between border-b border-white/10 bg-[#080808]/95 px-5 py-4 backdrop-blur">
                <div className="flex min-w-0 items-center gap-3">
                  <SourceLogo source={detailPressRelease.source} />
                  <span className="shrink-0 text-[10px] font-sans uppercase tracking-[0.22em] text-accent/70">
                    {detailPressRelease.date}
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => setDetailPressRelease(null)}
                  className="flex h-8 w-8 items-center justify-center rounded-sm border border-white/10 text-white/55 hover:border-white/30 hover:text-white"
                  aria-label="닫기"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>

              <div className="space-y-5 p-5 sm:p-6">
                {detailImages.length > 0 && (
                  <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_120px]">
                    <div className="overflow-hidden rounded-sm border border-white/10 bg-white/[0.03]">
                      <img
                        src={detailImages[0]}
                        alt=""
                        referrerPolicy="no-referrer"
                        className="max-h-[320px] w-full object-contain"
                      />
                    </div>
                    {detailImages.length > 1 && (
                      <div className="grid grid-cols-3 gap-2 sm:grid-cols-1">
                        {detailImages.slice(1, 4).map((url) => (
                          <div key={url} className="h-20 overflow-hidden rounded-sm border border-white/10 bg-white/[0.03]">
                            <img
                              src={url}
                              alt=""
                              referrerPolicy="no-referrer"
                              className="h-full w-full object-cover"
                            />
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}

                <div className="space-y-3">
                  <div className="text-[10px] font-sans uppercase tracking-[0.24em] text-accent">
                    Source Detail
                  </div>
                  <h3 className="text-xl sm:text-2xl font-sans font-bold leading-snug text-white">
                    {detailPressRelease.title}
                  </h3>
                  {detailPressRelease.summary && (
                    <p className="whitespace-pre-wrap text-[14px] leading-relaxed text-white/65">
                      {detailPressRelease.summary}
                    </p>
                  )}
                </div>

                <div className="flex flex-wrap items-center gap-2 border-t border-white/10 pt-4">
                  {detailPressRelease.detail_url && (
                    <a
                      href={detailPressRelease.detail_url}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1.5 rounded-sm border border-white/15 px-3 py-2 text-[10px] font-sans uppercase tracking-[0.18em] text-white/75 hover:border-white/35 hover:text-white"
                    >
                      원문 보기 <ExternalLink className="h-3 w-3" />
                    </a>
                  )}
                  <button
                    type="button"
                    onClick={() => {
                      const target = detailPressRelease;
                      setDetailPressRelease(null);
                      handleSelectPR(target);
                    }}
                    className="inline-flex items-center gap-1.5 rounded-sm bg-white px-3 py-2 text-[10px] font-sans font-bold uppercase tracking-[0.18em] text-black hover:bg-white/90"
                  >
                    이 소스 선택 <ArrowRight className="h-3 w-3" />
                  </button>
                </div>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

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
                  <button className="flex items-center gap-1.5 text-[10px] tracking-[0.1em] font-sans text-accent bg-white/5 border border-white/10 px-2 py-1 hover:bg-white/10 hover:text-ink transition-all duration-300 rounded-sm" onClick={() => setLastUpdated(formatUpdatedAt(new Date()))}>
                    <RefreshCcw className="w-2.5 h-2.5" />
                    업데이트 : {lastUpdated}
                  </button>
                </div>
                <div className="relative w-full sm:w-64 group">
                  <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-accent group-focus-within:text-ink transition-colors" />
                  <input
                    type="text"
                    value={pressQuery}
                    onChange={(e) => setPressQuery(e.target.value)}
                    placeholder="검색어 입력..."
                    className="w-full bg-white/[0.02] border border-white/10 text-ink text-xs pl-9 pr-3 py-2 outline-none focus:border-white/40 focus:bg-white/[0.05] transition-all placeholder:text-white/20 rounded-sm"
                  />
                </div>
              </div>

              {!isLoadingPRs && !prsError && pressReleases.length > 0 && (
                <div className="space-y-2 border-y border-white/10 py-3">
                  <div className="flex items-center justify-between text-[9px] font-sans uppercase tracking-[0.2em] text-accent/70">
                    <span>수집처 필터</span>
                    <span>{filteredPressReleases.length} / {pressReleases.length}건</span>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <button
                      type="button"
                      onClick={() => setSelectedSourceFilter('all')}
                      className={`rounded-sm border px-3 py-1.5 text-[10px] font-sans font-bold uppercase tracking-[0.16em] transition-all ${
                        selectedSourceFilter === 'all'
                          ? 'border-white/60 bg-white/[0.16] text-white shadow-[0_0_14px_rgba(255,255,255,0.16)]'
                          : 'border-white/10 bg-white/[0.03] text-white/55 hover:border-white/30 hover:text-white'
                      }`}
                    >
                      전체 <span className="ml-1 font-mono opacity-60">{pressReleases.length}</span>
                    </button>
                    {SOURCE_COLUMNS.map((column) => {
                      const count = pressReleases.filter((pr) => resolveSourceColumnKey(pr.source) === column.key).length;
                      const active = selectedSourceFilter === column.key;
                      return (
                        <button
                          key={column.key}
                          type="button"
                          onClick={() => setSelectedSourceFilter(column.key)}
                          className={`flex items-center gap-2 rounded-sm border px-3 py-1.5 transition-all ${
                            active
                              ? 'border-white/60 bg-white/[0.16] text-white shadow-[0_0_14px_rgba(255,255,255,0.16)]'
                              : 'border-white/10 bg-white/[0.03] text-white/55 hover:border-white/30 hover:text-white'
                          }`}
                        >
                          <SourceLogo source={column.sourceForLogo} />
                          <span className="text-[10px] font-sans font-bold tracking-[0.1em]">{column.label}</span>
                          <span className="font-mono text-[9px] opacity-60">{count}</span>
                        </button>
                      );
                    })}
                  </div>
                </div>
              )}

              <div className="space-y-3">
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
                {!isLoadingPRs && !prsError && pressReleases.length > 0 && filteredPressReleases.length === 0 && (
                  <div className="text-center py-10 text-[11px] font-sans uppercase tracking-[0.2em] text-white/40">
                    조건에 맞는 보도자료가 없습니다
                  </div>
                )}
                {!isLoadingPRs && !prsError && filteredPressReleases.map((pr, idx) => (
                  <motion.div
                    key={pr.id}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.4, delay: idx * 0.05, ease: "easeOut" }}
                    onClick={() => handleSelectPR(pr)}
                    className="group relative bg-white/[0.015] border border-white/10 hover:bg-white/[0.04] hover:border-white/30 transition-all duration-300 p-3 sm:py-3 sm:px-4 flex flex-col sm:flex-row gap-3 items-start cursor-pointer overflow-visible rounded-[2px]"
                  >
                    <div className="absolute left-0 top-0 bottom-0 w-[3px] bg-white/0 group-hover:bg-white/40 transition-colors duration-300" />

                    {pr.thumbnailUrl && (
                      <div className="group/thumb relative z-20 shrink-0 w-full sm:w-[112px] h-32 sm:h-[112px] overflow-visible rounded-[2px]">
                        <div className="h-full w-full overflow-hidden rounded-[2px] bg-white/[0.03] border border-white/10">
                          <img
                            src={pr.thumbnailUrl}
                            alt=""
                            loading="lazy"
                            referrerPolicy="no-referrer"
                            onError={(e) => {
                              (e.currentTarget.closest('.group\\/thumb') as HTMLElement | null)?.style.setProperty('display', 'none');
                            }}
                            className="w-full h-full object-cover opacity-80 group-hover:opacity-100 transition-opacity rounded-[2px]"
                          />
                        </div>
                        <div className="pointer-events-none absolute left-full top-1/2 z-[120] ml-5 hidden w-[420px] -translate-y-1/2 overflow-hidden rounded-[3px] border border-white/25 bg-black shadow-[0_30px_100px_rgba(0,0,0,0.85),0_0_45px_rgba(255,255,255,0.12)] sm:group-hover/thumb:block">
                          <img
                            src={pr.thumbnailUrl}
                            alt=""
                            referrerPolicy="no-referrer"
                            className="max-h-[340px] w-full object-contain bg-black"
                          />
                        </div>
                      </div>
                    )}

                    <div className="min-w-0 flex-1 space-y-1.5 w-full pl-1.5">
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
                      <h4 className="text-[17px] sm:text-[19px] font-sans font-[700] text-white/90 group-hover:text-white transition-colors tracking-tight leading-snug drop-shadow-sm line-clamp-2">{pr.title}</h4>
                      <p className="text-[13px] font-sans font-normal text-white/60 max-w-5xl leading-relaxed line-clamp-2">{pr.summary}</p>
                    </div>
                    <div className="flex shrink-0 flex-row flex-wrap gap-2 items-start justify-start opacity-55 transition-opacity group-hover:opacity-100 sm:min-h-[112px] sm:w-28 sm:flex-col sm:items-end sm:justify-between sm:pt-1.5">
                      <button
                        type="button"
                        onClick={(e) => {
                          e.stopPropagation();
                          setDetailPressRelease(pr);
                        }}
                        className="text-[9px] uppercase tracking-[0.2em] font-sans text-accent hover:text-ink flex items-center gap-1.5 transition-all hover:gap-2"
                      >
                        자세히 보기 <Info className="w-2.5 h-2.5" />
                      </button>
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
                  <input
                    type="text"
                    value={relatedQuery}
                    onChange={(e) => setRelatedQuery(e.target.value)}
                    placeholder="기사 검색..."
                    className="w-full bg-white/[0.02] border border-white/10 text-ink text-xs pl-9 pr-3 py-2 outline-none focus:border-white/40 focus:bg-white/[0.05] transition-all placeholder:text-white/20 rounded-sm"
                  />
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
                {!isLoadingRelated && relatedArticles.length > 0 && filteredRelatedArticles.length === 0 && (
                  <div className="text-center py-10 text-[11px] font-sans uppercase tracking-[0.2em] text-white/40">
                    검색 결과가 없습니다
                  </div>
                )}
                {!isLoadingRelated && filteredRelatedArticles.map((article, idx) => {
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
                      {article.detail_url ? (
                        <a
                          href={article.detail_url}
                          target="_blank"
                          rel="noreferrer"
                          onClick={(e) => e.stopPropagation()}
                          className="hidden sm:flex text-[9px] font-sans uppercase tracking-[0.2em] text-accent hover:text-ink items-center gap-1.5 transition-all hover:gap-2 opacity-40 group-hover:opacity-100 z-10"
                          aria-label={`${article.title} 원문 보기`}
                        >
                          원문 <ExternalLink className="w-2.5 h-2.5" />
                        </a>
                      ) : (
                        <span className="hidden sm:flex text-[9px] font-sans uppercase tracking-[0.2em] text-white/25 items-center gap-1.5 opacity-40 z-10">
                          원문 없음
                        </span>
                      )}
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

                <div className="relative z-10 space-y-4 pt-3 border-t border-white/10">
                  <label className="space-y-2">
                    <span className="block text-[10px] tracking-[0.2em] font-sans text-accent">
                      생성 모델
                    </span>
                    <select
                      value={selectedModelKey}
                      onChange={(e) => setSelectedModelKey(e.target.value)}
                      className="w-full bg-white/[0.03] border border-white/15 text-white text-sm font-sans px-3 py-3 outline-none focus:border-white/40 rounded-sm"
                    >
                      {llmModels.map((model) => (
                        <option key={model.key} value={model.key} className="bg-[#101010]">
                          {model.label}
                        </option>
                      ))}
                    </select>
                  </label>

                  <label className="block space-y-2">
                    <span className="block text-[10px] tracking-[0.2em] font-sans text-accent">
                      기사 스타일
                    </span>
                    <select
                      value={articleStyle}
                      onChange={(e) => setArticleStyle(e.target.value as ArticleStyle)}
                      className="w-full bg-white/[0.03] border border-white/15 text-white text-sm font-sans px-3 py-3 outline-none focus:border-white/40 rounded-sm"
                    >
                      <option value="default" className="bg-[#101010]">일반 뉴스</option>
                      <option value="mediaus_song" className="bg-[#101010]">미디어스 — 송창한</option>
                      <option value="mediaus_ko" className="bg-[#101010]">미디어스 — 고성욱</option>
                    </select>
                  </label>

                  <label className="block space-y-2">
                    <span className="block text-[10px] tracking-[0.2em] font-sans text-accent">
                      말투
                    </span>
                    <select
                      value={articleTone}
                      onChange={(e) => setArticleTone(e.target.value as ArticleTone)}
                      className="w-full bg-white/[0.03] border border-white/15 text-white text-sm font-sans px-3 py-3 outline-none focus:border-white/40 rounded-sm"
                    >
                      {ARTICLE_TONE_OPTIONS.map((option) => (
                        <option key={option.value} value={option.value} className="bg-[#101010]">
                          {option.label} - {option.description}
                        </option>
                      ))}
                    </select>
                  </label>
                </div>

                {llmModelsError && (
                  <div className="relative z-10 border border-red-400/20 bg-red-500/10 px-4 py-3 text-left text-[12px] font-sans text-red-200 rounded-sm">
                    {llmModelsError}
                  </div>
                )}
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

              <AnimatePresence>
                {isGenerating && (
                  <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    className="fixed inset-0 z-[80] flex items-center justify-center bg-black/75 px-4 backdrop-blur-md"
                  >
                    <motion.div
                      initial={{ opacity: 0, y: 18, scale: 0.98 }}
                      animate={{ opacity: 1, y: 0, scale: 1 }}
                      exit={{ opacity: 0, y: 10, scale: 0.99 }}
                      transition={{ duration: 0.25, ease: 'easeOut' }}
                      className="w-full max-w-3xl overflow-hidden rounded-sm border border-white/15 bg-[#070707]/95 text-left shadow-[0_30px_120px_rgba(0,0,0,0.75),0_0_50px_rgba(255,255,255,0.06)]"
                    >
                      <div className="flex items-center justify-between border-b border-white/10 px-5 py-4">
                        <div>
                          <div className="text-[10px] font-sans uppercase tracking-[0.28em] text-accent">
                            Generation Stream
                          </div>
                          <div className="mt-1 text-sm font-sans font-bold text-white/90">
                            기사 생성 진행 중
                          </div>
                        </div>
                        <div className="flex items-center gap-2 text-[9px] font-sans uppercase tracking-[0.24em] text-green-300/80">
                          <span className="h-1.5 w-1.5 rounded-full bg-green-400 shadow-[0_0_10px_rgba(74,222,128,0.8)]" />
                          Live
                        </div>
                      </div>

                      <div className="max-h-[78vh] space-y-5 overflow-y-auto px-5 py-5">
                        <div className="space-y-2.5">
                          {GENERATION_FLOW.map((item, idx) => {
                            const latestStep = generationSteps[generationSteps.length - 1];
                            const currentIndex = Math.max(
                              0,
                              GENERATION_FLOW.findIndex((stepItem) => stepItem.stage === latestStep?.stage),
                            );
                            const currentStage = latestStep?.stage ?? 'extracting';
                            const receivedStep = [...generationSteps]
                              .reverse()
                              .find((stepItem) => stepItem.stage === item.stage);
                            const message = receivedStep?.message ?? item.message;
                            const isComplete = currentStage === 'complete';
                            const isCurrent = item.stage === currentStage && !isComplete;
                            const isDone = isComplete || idx < currentIndex;
                            const isPending = !isCurrent && !isDone;
                            return (
                              <motion.div
                                key={item.stage}
                                initial={false}
                                animate={{ opacity: isPending ? 0.45 : 1, x: 0 }}
                                className={`flex items-start gap-3 text-[12px] font-sans tracking-[0.02em] transition-colors ${
                                  isCurrent ? 'text-white/90' : isDone ? 'text-white/55' : 'text-white/30'
                                }`}
                              >
                                <span className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center">
                                  {isDone ? (
                                    <CheckCircle2 className="h-4 w-4 text-green-400 drop-shadow-[0_0_8px_rgba(74,222,128,0.45)]" />
                                  ) : isCurrent ? (
                                    <RefreshCcw className="h-3.5 w-3.5 animate-spin text-white/85" />
                                  ) : (
                                    <span className="h-3.5 w-3.5 rounded-full border border-white/20 bg-white/[0.03]" />
                                  )}
                                </span>
                                <span>{message}</span>
                              </motion.div>
                            );
                          })}
                          {generationSteps.length === 0 && (
                            <div className="flex items-center gap-3 text-[12px] font-sans text-white/80">
                              <RefreshCcw className="h-3.5 w-3.5 animate-spin" />
                              {generationStatus}
                            </div>
                          )}
                        </div>

                        {generationPreview && (
                          <div className="border-t border-white/10 pt-4">
                            <div className="mb-2 text-[10px] font-sans uppercase tracking-[0.22em] text-accent/80">
                              Streaming Draft
                            </div>
                            <pre
                              ref={generationPreviewRef}
                              className="max-h-[34vh] min-h-[180px] overflow-y-auto scroll-smooth whitespace-pre-wrap rounded-sm border border-white/10 bg-white/[0.025] p-4 text-[12px] leading-relaxed font-sans text-white/65"
                            >
                              {generationPreview}
                            </pre>
                          </div>
                        )}
                      </div>
                    </motion.div>
                  </motion.div>
                )}
              </AnimatePresence>

              {generateError && (
                <div className="border border-red-400/20 bg-red-500/10 px-4 py-3 text-left text-[12px] font-sans text-red-200 rounded-sm">
                  {generateError}
                </div>
              )}
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
                    <button
                      type="button"
                      onClick={exportArticleToWord}
                      disabled={!generated || isExportingWord}
                      className="text-[9px] tracking-[0.2em] font-sans px-3 py-1.5 transition-all font-bold rounded-sm bg-white text-black hover:bg-white/90 border border-white/20 hover:border-transparent flex items-center gap-1.5 disabled:cursor-not-allowed disabled:opacity-45"
                    >
                      <Download className="w-3 h-3" /> {isExportingWord ? '내보내는 중' : '워드로 내보내기'}
                    </button>
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

                {exportError && (
                  <div className="mb-4 rounded-sm border border-amber-300/20 bg-amber-400/10 px-3 py-2 text-[11px] font-sans text-amber-100/85">
                    {exportError}
                  </div>
                )}

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
                    {isEditing ? (
                      <textarea
                        value={generated?.lead ?? ''}
                        onChange={(e) => setGenerated((g) => g ? { ...g, lead: e.target.value } : g)}
                        className="w-full bg-transparent text-base sm:text-[17px] font-sans font-medium text-orange-400 leading-relaxed outline-none transition-all resize-none min-h-[90px] px-2 border-l-2 border-white/60 focus:bg-white/[0.03] py-2 rounded-sm"
                      />
                    ) : (
                      <>
                        <BodyWithCitations
                          body={generated?.lead ?? ''}
                          citations={generated?.citations ?? {}}
                          fallbackCitationId="1"
                          appendFallbackWhenUncited
                          className="w-full bg-transparent text-base sm:text-[17px] font-sans font-medium text-orange-400 leading-relaxed px-2 py-1 whitespace-pre-wrap"
                        />
                        {leadImages.length > 0 && (
                          <div className="mt-4 space-y-4 px-2">
                            {leadImages.map(renderInsertedImage)}
                          </div>
                        )}
                      </>
                    )}
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
                        fallbackCitationId="1"
                        appendFallbackWhenUncited
                        paragraphInserts={Object.fromEntries(
                          Object.entries(bodyImageInserts).map(([idx, images]) => [
                            Number(idx),
                            images.map(renderInsertedImage),
                          ]),
                        )}
                      />
                    )}
                  </motion.div>
                </div>
              </div>

              {/* Sidebar */}
              <motion.div initial={{opacity:0, x:20}} animate={{opacity:1,x:0}} transition={{delay:0.5}} className="space-y-4">
                <div className="border border-white/10 bg-white/[0.02] p-5 space-y-4 backdrop-blur-md rounded-sm">
                  <h4 className="text-[10px] tracking-[0.2em] text-accent border-b border-white/10 font-sans pb-3 flex items-center gap-2">
                    <ImageIcon className="w-3 h-3" /> 이미지 삽입
                  </h4>

                  <label className="block space-y-2">
                    <span className="text-[9px] uppercase tracking-[0.18em] text-white/35 font-sans">
                      삽입 위치
                    </span>
                    <select
                      value={imagePlacement}
                      onChange={(e) => setImagePlacement(e.target.value as ImagePlacement)}
                      className="w-full rounded-sm border border-white/15 bg-black/30 px-3 py-2 text-[11px] font-sans text-white outline-none focus:border-white/40"
                    >
                      {imageTargets.map((target) => (
                        <option key={target.value} value={target.value} className="bg-[#101010]">
                          {target.label}
                        </option>
                      ))}
                    </select>
                  </label>

                  {availableArticleImages.length > 0 ? (
                    <div className="grid gap-2">
                      {availableArticleImages.map((asset) => (
                        <div
                          key={asset.id}
                          className="grid grid-cols-[72px_1fr] gap-3 rounded-[2px] border border-white/5 bg-black/20 p-2"
                        >
                          <img
                            src={asset.url}
                            alt={asset.title}
                            className="h-[56px] w-[72px] rounded-[2px] border border-white/10 object-cover"
                            loading="lazy"
                          />
                          <div className="min-w-0 space-y-2">
                            <div className="flex items-center gap-2 text-[9px] uppercase tracking-[0.16em] text-accent/70">
                              <span>{asset.sourceLabel}</span>
                              <span className="text-white/25">{asset.source}</span>
                            </div>
                            <div className="line-clamp-2 text-[11px] leading-snug text-white/60">
                              {asset.title}
                            </div>
                            <button
                              type="button"
                              onClick={() => insertArticleImage(asset)}
                              className="inline-flex items-center gap-1 rounded-sm border border-white/15 px-2 py-1 text-[9px] font-sans uppercase tracking-[0.16em] text-white/70 transition-colors hover:border-white/40 hover:bg-white hover:text-black"
                            >
                              <Plus className="h-3 w-3" /> 삽입
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="rounded-sm border border-white/5 bg-black/20 px-3 py-4 text-[11px] leading-relaxed text-white/40">
                      선택한 소스에서 사용할 수 있는 이미지가 없습니다.
                    </div>
                  )}

                  {insertedImages.length > 0 && (
                    <div className="border-t border-white/10 pt-3">
                      <div className="mb-2 text-[9px] uppercase tracking-[0.18em] text-white/35 font-sans">
                        삽입된 이미지 {insertedImages.length}개
                      </div>
                      <div className="space-y-1.5">
                        {insertedImages.map((image) => (
                          <div
                            key={image.insertId}
                            className="flex items-center justify-between gap-2 rounded-[2px] border border-white/5 bg-black/20 px-2 py-1.5"
                          >
                            <span className="min-w-0 truncate text-[10px] text-white/55">
                              {imageTargets.find((target) => target.value === image.placement)?.label ?? '본문'}
                            </span>
                            <button
                              type="button"
                              onClick={() => removeArticleImage(image.insertId)}
                              className="shrink-0 text-white/40 hover:text-white"
                              aria-label="삽입 이미지 삭제"
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                            </button>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>

                <div className="border border-white/10 bg-white/[0.02] p-5 space-y-4 backdrop-blur-md rounded-sm">
                  <h4 className="text-[10px] tracking-[0.2em] text-accent border-b border-white/10 font-sans pb-3 flex items-center gap-2">
                    <Info className="w-3 h-3" /> 사용한 소스
                  </h4>

                  <div className="border-l-[3px] border-white/30 pl-3 py-1">
                    <div className="mb-2 flex flex-wrap items-center gap-2 text-[9px] tracking-[0.16em] text-white/35 font-sans uppercase">
                      메인 보도자료
                      <SourceLogo source={selectedPR.source} />
                      <span>{selectedPR.date}</span>
                    </div>
                    <a
                      href={selectedPR.detail_url || '#'}
                      target={selectedPR.detail_url ? '_blank' : undefined}
                      rel={selectedPR.detail_url ? 'noreferrer' : undefined}
                      className="block text-[13px] font-sans font-bold leading-snug text-white/85 hover:text-white transition-colors"
                    >
                      {selectedPR.title}
                    </a>
                  </div>

                  {selectedArticles.length > 0 && (
                    <div className="border-t border-white/10 pt-4">
                      <div className="mb-2 text-[9px] tracking-[0.18em] text-white/35 font-sans uppercase">
                        선택한 관련기사 {selectedArticles.length}개
                      </div>
                      <div className="grid gap-2">
                        {selectedArticles.map((article, idx) => (
                          <a
                            key={article.id}
                            href={article.detail_url || '#'}
                            target={article.detail_url ? '_blank' : undefined}
                            rel={article.detail_url ? 'noreferrer' : undefined}
                            className="group/link grid grid-cols-[auto_1fr] gap-x-2 gap-y-1 rounded-[2px] border border-white/5 bg-black/20 px-3 py-2 hover:border-white/15 hover:bg-white/[0.035] transition-colors"
                          >
                            <span className="text-[10px] font-sans text-accent/60 font-bold">[{idx + 1}]</span>
                            <div className="min-w-0 space-y-1">
                              <div className="flex min-w-0 items-center gap-2">
                                <SourceLogo source={article.source} />
                                <span className="shrink-0 text-[9px] font-sans text-white/30 tracking-[0.12em]">
                                  {article.date}
                                </span>
                              </div>
                              <div className="line-clamp-2 text-[12px] leading-snug text-white/60 group-hover/link:text-white/90 transition-colors">
                                {article.title}
                              </div>
                            </div>
                          </a>
                        ))}
                      </div>
                    </div>
                  )}
                </div>

              </motion.div>
            </motion.div>
          )}

        </AnimatePresence>
      </div>
    </section>
  );
}
