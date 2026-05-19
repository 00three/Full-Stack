const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE || '/api';

export interface PressRelease {
  id: string;
  title: string;
  source: string;
  date: string;
  summary: string;
  detail_url: string;
  isNew: boolean;
  thumbnailUrl?: string;
  imageUrls?: string[];
}

export interface RelatedArticle {
  id: string;
  title: string;
  source: string;
  date: string;
  source_release_id?: string;
  source_release_title?: string;
  detail_url?: string;
  document_kind?: string;
}

export interface Citation {
  category: string;
  title: string;
  date: string;
  url: string;
}

export interface GeneratedArticle {
  article_id?: string;
  genre?: string;
  title: string;
  lead: string;
  body: string;
  citations: Record<string, Citation>;
}

export interface LLMModelOption {
  key: string;
  label: string;
  provider: string;
  family: string;
}

export interface LLMModelCatalog {
  default_model_key: string;
  models: LLMModelOption[];
}

export type GenerationStreamEvent =
  | { type: 'stage'; stage: string; message: string; extracted_json?: Record<string, unknown> }
  | { type: 'token'; delta: string }
  | { type: 'complete'; article: GeneratedArticle }
  | { type: 'error'; message: string };

interface PressReleaseRaw {
  id: string;
  title: string;
  source: string;
  date: string;
  summary?: string;
  detail_url?: string;
  is_new?: boolean;
  thumbnail_url?: string | null;
  image_urls?: string[];
}

function normalizePressRelease(raw: PressReleaseRaw): PressRelease {
  return {
    id: raw.id,
    title: raw.title,
    source: raw.source,
    date: raw.date,
    summary: raw.summary ?? '',
    detail_url: raw.detail_url ?? '',
    isNew: !!raw.is_new,
    thumbnailUrl: raw.thumbnail_url ?? undefined,
    imageUrls: Array.isArray(raw.image_urls) ? raw.image_urls : undefined,
  };
}

export async function fetchPressReleases(query?: string): Promise<PressRelease[]> {
  const url = query
    ? `${API_BASE}/press-releases?q=${encodeURIComponent(query)}`
    : `${API_BASE}/press-releases`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`fetchPressReleases: ${res.status}`);
  const data: PressReleaseRaw[] = await res.json();
  return data.map(normalizePressRelease);
}

export async function fetchRelatedArticles(
  pressReleaseId: string,
): Promise<RelatedArticle[]> {
  const url = `${API_BASE}/press-releases/related?ids=${encodeURIComponent(pressReleaseId)}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error(`fetchRelatedArticles: ${res.status}`);
  const data = await res.json();
  return (data.related ?? []) as RelatedArticle[];
}

export async function fetchLLMModels(): Promise<LLMModelCatalog> {
  const res = await fetch(`${API_BASE}/llm/models`);
  if (!res.ok) throw new Error(`fetchLLMModels: ${res.status}`);
  return (await res.json()) as LLMModelCatalog;
}

export async function generateArticle(
  pressReleaseIds: string[],
  relatedArticleIds: string[],
  createdBy?: string,
  modelKey?: string,
  articleStyle?: 'default' | 'mediaus',
): Promise<GeneratedArticle> {
  const res = await fetch(`${API_BASE}/articles/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      press_release_ids: pressReleaseIds,
      related_article_ids: relatedArticleIds,
      created_by: createdBy || null,
      model_key: modelKey || null,
      article_style: articleStyle || null,
    }),
  });
  if (!res.ok) throw new Error(`generateArticle: ${res.status}`);
  return (await res.json()) as GeneratedArticle;
}

export async function generateArticleStream(
  pressReleaseIds: string[],
  relatedArticleIds: string[],
  createdBy: string | undefined,
  modelKey: string | undefined,
  articleStyle: 'default' | 'mediaus',
  onEvent: (event: GenerationStreamEvent) => void,
): Promise<GeneratedArticle> {
  const res = await fetch(`${API_BASE}/articles/generate/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      press_release_ids: pressReleaseIds,
      related_article_ids: relatedArticleIds,
      created_by: createdBy || null,
      model_key: modelKey || null,
      article_style: articleStyle,
    }),
  });
  if (!res.ok) throw new Error(`generateArticleStream: ${res.status}`);
  if (!res.body) throw new Error('generateArticleStream: empty body');

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let completed: GeneratedArticle | null = null;

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const frames = buffer.split('\n\n');
    buffer = frames.pop() ?? '';

    for (const frame of frames) {
      const payload = frame
        .split('\n')
        .find((line) => line.startsWith('data: '))
        ?.slice(6);
      if (!payload) continue;
      const event = JSON.parse(payload) as GenerationStreamEvent;
      onEvent(event);
      if (event.type === 'error') throw new Error(event.message);
      if (event.type === 'complete') completed = event.article;
    }
  }

  if (!completed) throw new Error('generateArticleStream: completion missing');
  return completed;
}
