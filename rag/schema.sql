-- =========================================================
-- RAG 속보기사 생성 시스템 — DB 스키마
--
-- 적용 방법 (pgAdmin):
--   1. pgAdmin → 본 DB 선택 → Tools → Query Tool
--   2. 이 파일 내용 전체 복붙 → ▶ 실행
--   3. AWS RDS로 옮길 때도 동일 파일 재실행
--
-- 사전 요구사항:
--   - PostgreSQL 14+
--   - pgvector 확장 (로컬: brew install pgvector / RDS: 콘솔에서 활성화)
-- =========================================================

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;  -- gen_random_uuid() 제공


-- =========================================================
-- 1. raw_documents — 크롤러 JSONL 1줄 = 1 row
-- =========================================================
CREATE TABLE IF NOT EXISTS raw_documents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    doc_id          VARCHAR(255) NOT NULL UNIQUE,       -- 크롤러 doc_id (멱등 INSERT 키)
    source          VARCHAR(255) NOT NULL,               -- KCC | NSP | MBC | NODONG | 외부 참고기사 출처
    document_kind   VARCHAR(32) NOT NULL DEFAULT 'press_release'
                    CHECK (document_kind IN ('press_release', 'reference_article')),
    parent_doc_id   VARCHAR(255),
    department      VARCHAR(255),
    author          VARCHAR(255),
    title           VARCHAR(500) NOT NULL,
    date            DATE,
    summary         TEXT,
    content_text    TEXT NOT NULL,                       -- 크롤러 content_text
    attachment_text TEXT,                                -- 크롤러 attachment_text (PDF/DOCX/HWP 추출본)
    detail_url      TEXT,
    image_urls      JSONB NOT NULL DEFAULT '[]'::jsonb,
    attachments     JSONB NOT NULL DEFAULT '[]'::jsonb,
    hashtags        JSONB NOT NULL DEFAULT '[]'::jsonb,
    "references"    JSONB NOT NULL DEFAULT '[]'::jsonb,  -- SQL 예약어 → 따옴표 필수
    crawled_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);


-- =========================================================
-- 2. documents — 청킹·임베딩된 검색 단위 (search.py 조회 대상)
-- =========================================================
CREATE TABLE IF NOT EXISTS documents (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    raw_document_id  UUID NOT NULL REFERENCES raw_documents(id) ON DELETE CASCADE,
    chunk_id         VARCHAR(64) NOT NULL UNIQUE,        -- 예: kcc_20260318_ab12cd34_001
    source           VARCHAR(255) NOT NULL,
    date             DATE,
    title            VARCHAR(500),
    data_type        VARCHAR(20) NOT NULL
                     CHECK (data_type IN ('body_text', 'pdf_text', 'table')),
    context_prefix   TEXT,                                -- 4단계: Contextual Retriever 결과 (없으면 빈 문자열)
    original_text    TEXT NOT NULL,                       -- 청크 원본
    full_text        TEXT NOT NULL,                       -- context_prefix + meta_prefix + original_text
    embedding_dense  VECTOR(1024) NOT NULL,               -- BGE-M3 dense
    -- 8단계 중복 병합: 같은 의미 chunk가 여러 raw_documents에 등장하면
    -- 첫 등장 chunk의 source_doc_ids에 후속 doc의 메타를 append.
    -- 형식: [{"doc_id":"...","source":"KCC","title":"...","date":"YYYY-MM-DD"}, ...]
    source_doc_ids   JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 인덱스: dense 코사인 유사도 검색 (search.py의 <=> 연산자)
CREATE INDEX IF NOT EXISTS idx_documents_embedding_dense
    ON documents USING hnsw (embedding_dense vector_cosine_ops);

-- 인덱스: tsvector 키워드 검색 (search.py의 to_tsvector('simple', full_text))
CREATE INDEX IF NOT EXISTS idx_documents_fulltext_gin
    ON documents USING gin (to_tsvector('simple', full_text));

-- 인덱스: FK 조인용
CREATE INDEX IF NOT EXISTS idx_documents_raw_doc
    ON documents(raw_document_id);


-- =========================================================
-- 3. generated_articles — LLM 생성 속보기사 + 출처 매핑
-- =========================================================
CREATE TABLE IF NOT EXISTS generated_articles (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    raw_document_id     UUID REFERENCES raw_documents(id) ON DELETE SET NULL,
    title               VARCHAR(500) NOT NULL,
    lead                TEXT,
    body                TEXT NOT NULL,
    source_mapping      JSONB NOT NULL DEFAULT '{}'::jsonb,  -- 문장별 chunk_id 매핑
    source_release_ids  JSONB NOT NULL DEFAULT '[]'::jsonb,  -- 선택된 보도자료 doc_id 목록
    selected_chunk_ids  JSONB NOT NULL DEFAULT '[]'::jsonb,  -- 기자가 선택한 참고자료
    citations           JSONB NOT NULL DEFAULT '{}'::jsonb,  -- 본문 인용 메타데이터
    extracted_json      JSONB,                                -- 1차 LLM JSON 결과
    llm_provider        VARCHAR(32),                          -- bedrock | openai | anthropic
    llm_model_id        VARCHAR(255),                         -- 실제 호출 modelId
    article_style       VARCHAR(32),                          -- default | mediaus
    article_tone        VARCHAR(32),                          -- default | professional | friendly | direct | distinctive | efficient | critical | mz
    status              VARCHAR(20) NOT NULL DEFAULT 'draft'
                        CHECK (status IN ('draft', 'saved', 'published')),
    created_by          VARCHAR(64),                          -- 기자 ID
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_articles_raw_doc
    ON generated_articles(raw_document_id);

-- 기존 로컬 DB 업그레이드용 idempotent migration
ALTER TABLE raw_documents
    ADD COLUMN IF NOT EXISTS document_kind VARCHAR(32) NOT NULL DEFAULT 'press_release';
ALTER TABLE raw_documents
    ADD COLUMN IF NOT EXISTS parent_doc_id VARCHAR(255);
ALTER TABLE raw_documents
    ALTER COLUMN source TYPE VARCHAR(255);
ALTER TABLE documents
    ALTER COLUMN source TYPE VARCHAR(255);
ALTER TABLE generated_articles
    ADD COLUMN IF NOT EXISTS source_release_ids JSONB NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE generated_articles
    ADD COLUMN IF NOT EXISTS citations JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE generated_articles
    ADD COLUMN IF NOT EXISTS llm_provider VARCHAR(32);
ALTER TABLE generated_articles
    ADD COLUMN IF NOT EXISTS llm_model_id VARCHAR(255);
ALTER TABLE generated_articles
    ADD COLUMN IF NOT EXISTS article_style VARCHAR(32);
ALTER TABLE generated_articles
    ADD COLUMN IF NOT EXISTS article_tone VARCHAR(32);

CREATE INDEX IF NOT EXISTS idx_raw_documents_kind
    ON raw_documents(document_kind);


-- =========================================================
-- 4. process_log — 단계별 처리 결과 기록
-- =========================================================
CREATE TABLE IF NOT EXISTS process_log (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    raw_document_id  UUID REFERENCES raw_documents(id) ON DELETE SET NULL,
    step             VARCHAR(32) NOT NULL
                     CHECK (step IN ('crawling', 'chunking', 'embedding',
                                     'llm_json', 'llm_article', 'verification')),
    status           VARCHAR(16) NOT NULL
                     CHECK (status IN ('success', 'fail', 'retry')),
    retry_count      INT NOT NULL DEFAULT 0,
    error_message    TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_process_log_raw_doc
    ON process_log(raw_document_id);


-- =========================================================
-- 검증 쿼리 — 실행 후 4 row 나오면 성공
-- =========================================================
-- SELECT tablename FROM pg_tables
-- WHERE schemaname='public'
--   AND tablename IN ('raw_documents','documents','generated_articles','process_log');
