const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000';

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
}

export interface Citation {
  category: string;
  title: string;
  date: string;
  url: string;
}

export interface GeneratedArticle {
  title: string;
  lead: string;
  body: string;
  citations: Record<string, Citation>;
}

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

export async function generateArticle(
  pressReleaseIds: string[],
  relatedArticleIds: string[],
): Promise<GeneratedArticle> {
  const res = await fetch(`${API_BASE}/articles/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      press_release_ids: pressReleaseIds,
      related_article_ids: relatedArticleIds,
    }),
  });
  if (!res.ok) throw new Error(`generateArticle: ${res.status}`);
  return (await res.json()) as GeneratedArticle;
}
