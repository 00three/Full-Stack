# RAG 모듈 작업 현황

> 브랜치: `rag` | 최종 작업일: 2026-03-19

---

## 1. 현재 완료된 작업

### 파일 구조

```
rag/
├── __init__.py          # 패키지 초기화
├── config.py            # 설정 (DB, OpenAI, 검색 파라미터)
├── search.py            # 검색 전체 (dense + tsvector + RRF + 시간가중치 + Re-ranking)
├── llm.py               # LLM 3단계 (JSON 추출 → 기사 생성 → 사실검증)
├── pipeline.py          # search + llm 연결하는 메인 진입점
├── requirements.txt     # 의존성 (psycopg2, openai, sentence-transformers)
└── RAG_작업현황.md       # 이 문서
```

### 각 파일 상세

#### config.py
- `DBConfig`: PostgreSQL 연결 정보 (환경변수 또는 기본값)
- `LLMConfig`: OpenAI API 키, 모델(gpt-4o-mini), temperature(0.3)
- `SearchConfig`: 검색 파라미터
  - RRF 가중치 (dense 0.5 / keyword 0.5)
  - 후보 수: 30개 → 15개 → 10개
  - 시간 감쇠 반감기: 365일

#### search.py
- `dense_search()`: pgvector 코사인 유사도 검색
- `keyword_search()`: PostgreSQL tsvector 키워드 검색
- `rrf_fusion()`: 두 검색 결과를 RRF로 합산 → 30개
- `apply_time_decay()`: 지수 감쇠 시간 가중치 적용 → 15개
- `rerank()`: klue-cross-encoder-v1로 Re-ranking → 10개
- `hybrid_search()`: 위 전체를 연결하는 통합 함수

#### llm.py
- `extract_json()`: 1차 LLM - chunk에서 핵심 팩트 JSON 추출 (who, policy, decision, target, numbers, origin, effect)
- `generate_article()`: 2차 LLM - JSON 기반 속보기사 생성 (제목/리드/본문)
- `verify_article()`: 3차 LLM - 1차 JSON vs 2차 기사 비교 사실검증
- `_call_llm()`: 공통 OpenAI 호출 (재시도 3회)
- JSON 파싱 실패 시 재요청 로직 포함

#### pipeline.py
- `run()`: 전체 파이프라인 실행
  - 입력: query_text, query_embedding, selected_indices(기자 선택)
  - 출력: search_results, selected_chunks, extracted_json, article, verification

---

## 2. 아직 안 한 작업 (TODO)

### 우선순위 높음 (팀원 합의 후)

- [ ] **DB 스키마 확정**: 백엔드 담당과 pgvector 테이블 구조 합의
  - documents 테이블 컬럼명, 타입 확인
  - search.py의 SQL 쿼리가 실제 테이블과 맞는지 검증
- [ ] **크롤링 데이터 형식 합의**: 크롤링/전처리 담당과 chunk 데이터 형식 확정
  - chunk_id 형식 (예: KCC_20260305_001)
  - original_text, full_text 구분
  - 메타데이터 필드 (source, date, title, data_type)
- [ ] **백엔드 API 연동**: 백엔드의 어댑터 패턴에 맞게 연결
  - `backend/adapters/`의 RAGService, ArticleGenerator 구현체 작성
  - 현재 Mock → rag 모듈 호출로 교체

### 우선순위 중간 (데이터 들어온 후)

- [ ] **프롬프트 튜닝**
  - JSON 추출: Few-shot 예시 추가
  - 기사 생성: 미디어스 스타일 예시 기사 3개 추가
  - 사실검증: 검증 항목별 점수화
- [ ] **citations 필드 추가**: llm.py의 generate_article 반환값에 출처 정보 포함
  - 백엔드가 기대하는 형식:
    ```json
    {
      "title": "...",
      "lead": "...",
      "body": "...[1]...[2]",
      "citations": {
        "1": { "category": "...", "title": "...", "date": "...", "url": "..." }
      }
    }
    ```
  - 현재는 title, lead, body만 반환 중
- [ ] **임베딩 함수**: query_text를 BGE-M3로 임베딩하는 유틸 함수 추가
  - 현재 pipeline.run()은 query_embedding을 외부에서 받음
  - BGE-M3 로딩 + encode 함수 필요

### 우선순위 낮음 (고도화)

- [ ] **RAGAS 평가 모듈**: 오프라인 실험용 스크립트
- [ ] **청킹 사이즈 실험**: 200 / 400 / 600자 비교
- [ ] **시간 가중치 실험**: 180 / 365 / 730일 비교
- [ ] **에러 핸들링 강화**: process_log 테이블 연동
- [ ] **Contextual Retriever**: 청킹 시 LLM으로 맥락 prefix 생성 (전처리 담당과 협의)

---

## 3. 백엔드 연동 시 참고 (README 부록 기반)

### 연동할 API 2개

| 기능 | API | 현재 상태 |
|------|-----|----------|
| 참고 기사 검색 | `GET /press-releases/related?ids=1,2,3` | Mock 사용 중 → search.py로 교체 |
| 기사 생성 | `POST /articles/generate` | Mock 사용 중 → llm.py로 교체 |

### 연동 파일

- `backend/adapters/providers.py` → RAGService Protocol
- `backend/routers/press_releases.py` → get_related_articles_batch 함수
- `backend/routers/articles.py` → generate_article 함수
- `backend/deps.py` → 의존성 주입 (Mock → 실제 구현체 교체)

### 검색 결과 반환 형식 (백엔드가 기대)

```json
{
  "id": "참고 기사 ID (= chunk_id)",
  "title": "제목",
  "source": "출처",
  "date": "날짜",
  "source_release_id": "연관 보도자료 ID (선택)",
  "source_release_title": "연관 보도자료 제목 (선택)"
}
```

---

## 4. 기술 스택 요약

| 분야 | 기술 | 비고 |
|------|------|------|
| DB | PostgreSQL + pgvector | dense 벡터 + tsvector 키워드 통합 |
| 임베딩 | BGE-M3 (1024차원) | 전처리 담당이 임베딩 생성 |
| 검색 | Hybrid (dense + tsvector) + RRF | search.py에 구현 |
| 시간 가중치 | 지수 감쇠 (half_life 365일) | search.py에 구현 |
| Re-ranking | bongsoo/klue-cross-encoder-v1 | search.py에 구현 |
| LLM | OpenAI gpt-4o-mini | llm.py에 구현 |
| 의존성 | psycopg2, openai, sentence-transformers | requirements.txt |

---

## 5. 실행 방법 (나중에 테스트 시)

```bash
# 1. rag 브랜치 확인
git checkout rag

# 2. 가상환경 생성 + 의존성 설치
python -m venv .venv
source .venv/bin/activate
pip install -r rag/requirements.txt

# 3. 환경변수 설정
export PG_HOST=localhost
export PG_PORT=5432
export PG_DATABASE=rag_db
export PG_USER=postgres
export PG_PASSWORD=postgres
export OPENAI_API_KEY=sk-...

# 4. 파이프라인 테스트 (pgvector에 데이터 있어야 함)
python -c "
from rag.pipeline import run
result = run(
    query_text='소상공인 정책 연장',
    query_embedding=[0.1] * 1024,  # 실제로는 BGE-M3 임베딩
)
print(result)
"
```

---

## 6. 팀원에게 공유할 내용

### 크롤링/전처리 담당에게
- pgvector `documents` 테이블에 데이터 넣어주면 검색 가능
- 필요한 컬럼: chunk_id, source, date, title, original_text, full_text, embedding_dense(1024차원)
- chunk_id 형식 합의 필요

### 백엔드 담당에게
- `rag/` 모듈 완성되면 `backend/adapters/`에서 import해서 사용
- 현재 Mock 데이터 → rag.pipeline.run()으로 교체
- citations 필드 형식 최종 확인 필요
