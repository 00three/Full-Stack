# RAG 모듈 작업 현황

> 브랜치: `rag` | 최종 갱신: 2026-05-09
> 본인 단독 트랙. EDA 레포(분류기)는 RAG 파이프라인에 사용하지 않음.

---

## 1. 완료 — 가이드 8단계 100% 구현

### 파일 구조 (rag/)

| 파일 | 역할 | 가이드 단계 |
|---|---|---|
| `schema.sql` | DDL: raw_documents/documents/generated_articles/process_log + pgvector + HNSW/GIN 인덱스 | DB |
| `config.py` | DBConfig / LLMConfig / SearchConfig + .env 자동 로드 | 공통 |
| `preprocess.py` | body+pdf 결합, HTML 제거, 숫자/단위 보존, source 정규화 | 1·2 |
| `chunker.py` | LangChain Recursive 청킹 (400자/overlap 100) | 3 |
| `contextualizer.py` | gpt-4o-mini로 chunk 맥락 prefix 생성, 토큰·비용 누적 | 4 |
| `embedder.py` | 메타prefix + full_text 조립 + BGE-M3 1024d 임베딩 + query encode 유틸 | 5·6·7 |
| `ingest.py` | UPSERT raw → chunk → embed → 코사인 0.95 dedup → INSERT documents | 8·전체 |
| `search.py` | dense + tsvector hybrid → RRF → 시간 가중치 → cross-encoder rerank | 검색 |
| `llm.py` | 1차 JSON 추출 → 2차 기사 생성 → 3차 사실검증 | 생성 |
| `pipeline.py` | 검색·LLM 통합 진입점 (query 자동 임베딩) | 통합 |
| `search_test.py` | 검색 동작 검증 단발 스크립트 | 검증 |
| `ERD.md` | DB 스키마 문서 (실데이터 매핑 반영) | 문서 |
| `팀원_가이드_전처리.md` / `팀원_가이드_크롤링.md` | 입출력 명세 (수정 X) | 문서 |
| `requirements.txt` | psycopg2 / pgvector / openai / FlagEmbedding / langchain / numpy / dotenv 등 | 의존성 |
| `data/results_2026-04-21.jsonl` | 크롤러 입력 (gitignored, 340건 2.3MB) | 데이터 |

### 풀 ingest 결과 (2026-05-09)

```
처리 docs       : 340
생성 chunks     : 2,978
신규 INSERT     : 2,032 (68%)
중복 병합       : 946 (32% — cross-source 중복)
에러            : 0
소요 시간       : 7,295s (~2시간)
contextualizer  : 2,978 calls, 7.6M+0.19M tokens, ~$1.26
```

### end-to-end 검증 (search → LLM)

- `python -m rag.search_test` — "방송 토론 지방선거" 쿼리로 10건 결과 확인
- 백엔드 + 프론트 띄워 OECD / 이동통신 / 한-인도 정상회담 등 다양한 query에서 정상 동작
- LLM 1차 JSON 추출 + 2차 기사 생성 모두 동작

---

## 2. 백엔드 어댑터 (backend/adapters/)

| 파일 | 역할 |
|---|---|
| `db_provider.py` | DBPressReleaseProvider — raw_documents 조회 (DISTINCT ON dedup) |
| `rag_service.py` | DBRAGService — hybrid_search 래퍼, 같은 article dedup, detail_url JOIN |
| `article_generator.py` | LLMArticleGenerator — extract_json + generate_article |
| `mock_provider.py` | Mock 3종 (USE_MOCK=1 토글용 fallback) |
| `providers.py` / `rag.py` / `generator.py` | Protocol 인터페이스 (변경 없음) |

`backend/deps.py` — 환경변수 `USE_MOCK`으로 Mock/실제 토글.
`backend/routers/press_releases.py` / `articles.py` — Mock 직접 사용 → DI 어댑터 호출로 교체.

---

## 3. 환경 / 실행 방법

### 사전 조건
- macOS + brew PostgreSQL 17 (running on `localhost:5432`)
- pgvector 0.8.2 (HNSW 지원)
- conda env `rag` (Python 3.11)
- `.env` 파일 (gitignored): PG_*, OPENAI_API_KEY

### 적재
```bash
conda activate rag
python -m rag.ingest                # 4단계 포함 (~$1, ~30분~1시간)
python -m rag.ingest --no-context   # 4단계 skip (무료, ~10분)
python -m rag.ingest --limit 5      # 디버그용
```

### 백엔드 + 프론트 (데모용)
```bash
# 터미널 1
conda activate rag
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

# 터미널 2
cd frontend && npm install && npm run dev
# → http://localhost:5173
```

---

## 4. 알려진 데이터 한계 (크롤러 측)

1. HWP는 PrvText 미리보기만 추출 (실본문 누락 가능)
2. 첨부파일 1개만 추출 (PDF > DOCX > HWPX > HWP 우선순위)
3. 표 데이터 별도 추출 안 됨 (텍스트로 평탄화)
4. 기존 샘플 JSONL에는 중복이 남아 있으나, 신규 크롤러는 회차별 batch + canonical URL + 안정 ID로 방지

---

## 5. TODO (데모 후 / 배포 단계)

### 즉시
- [ ] LLM 프롬프트 강화: 출처 마커 `[1]` 누락·추측성 표현 잡기
- [x] `340 → 220` 차이 원인 확인: 일자별 append JSONL 중복 + KCC `jsessionid` URL 변형

### 백엔드 연동 후
- [ ] AWS RDS 마이그레이션 (백엔드 팀원, 동일 schema.sql 재실행)
- [ ] EC2에서 ingest 자동화 (cron 또는 크롤러 후속 트리거)
- [ ] 백엔드 Docker 이미지에 RAG 의존성 포함 (현재 host에서만 실행됨)

### 검색 품질 고도화
- [ ] 청킹 사이즈 실험 (200/400/600 비교)
- [ ] 시간 가중치 반감기 실험 (180/365/730일)
- [ ] Contextual Retriever 프롬프트 튜닝
- [ ] RAGAS 평가 모듈 추가

### 데이터 품질
- [ ] 크롤러: HWP 본문 풀 추출 (pyhwp BodyText 파싱)
- [ ] 크롤러: 첨부파일 모두 추출
- [ ] 크롤러: URL 정규화로 doc_id 중복 차단
- [ ] 표 데이터(`table_natural`) 추출 추가

---

## 6. 참고

- 가이드 명세: `rag/팀원_가이드_전처리.md` (8단계 입출력 정의)
- ERD: `rag/ERD.md` (DB 스키마 + 컬럼 의미)
- 크롤러 레포: `https://github.com/capstone-bigdata-team/Crawler`
- EDA 레포: `https://github.com/capstone-bigdata-team/EDA` (RAG와 무관)
