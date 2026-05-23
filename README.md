<div align="center">

# 속보생성 보조시스템

보도자료 기반 RAG 속보기사 자동 생성 플랫폼

</div>

## Docker 기반 전체 흐름

```text
Crawler
  -> shared outbox(batch JSONL)
  -> ingest-worker
  -> PostgreSQL + pgvector
  -> FastAPI backend
  -> Next.js frontend
```

두 레포는 분리 유지합니다.

- `Full-Stack`: `backend`, `frontend`, `rag`, `docker-compose.yml`
- `Crawler`: 수집기 소스. compose에서 sibling repo를 build context로 사용

## 빠른 시작

사전 조건:

- `Full-Stack`과 `Crawler` 레포가 같은 상위 폴더 아래에 있어야 합니다.
- 기본 DB는 Docker Compose 안의 PostgreSQL입니다.

```bash
cp .env.example .env
docker compose up --build
```

접속:

- 프론트엔드: `http://localhost:3000`
- 백엔드 문서: `http://localhost:8000/docs`
- PostgreSQL 호스트 포트: 기본 `5433` (`PG_HOST_PORT`로 변경)

주요 서비스:

| 서비스 | 역할 |
|---|---|
| `postgres` | PostgreSQL 17 + pgvector |
| `crawler` | 10분 주기 수집, batch JSONL 생성 |
| `ingest-worker` | outbox 감시 후 RAG 적재 |
| `backend` | FastAPI + RAG 검색 + 기사 생성/저장 |
| `frontend` | Next.js UI |

## 데이터 저장

| 테이블 | 저장 단위 |
|---|---|
| `raw_documents` | 원 보도자료와 외부 참고기사 원문 |
| `documents` | RAG 검색용 청크 |
| `generated_articles` | 생성 기사 초안, 선택 문서, 인용, 기자명 |
| `process_log` | 예약된 처리 로그 테이블 |

`raw_documents.document_kind`:

- `press_release`: 기자가 선택하는 원 보도자료
- `reference_article`: 외부 링크에서 수집한 참고기사

보도자료 목록 API는 `press_release`만 노출하고, RAG 검색 코퍼스는 두 종류를 모두 사용합니다.

## API

| Method | 경로 | 설명 |
|---|---|---|
| `GET` | `/press-releases?q=` | 보도자료 목록 |
| `GET` | `/press-releases/{id}` | 보도자료 상세 |
| `GET` | `/press-releases/related?ids=` | 관련기사 + 핵심 JSON |
| `GET` | `/llm/models` | 기사 생성 UI용 모델 허용목록 |
| `POST` | `/articles/generate` | 기사 생성 + `generated_articles` 저장 |
| `POST` | `/articles/generate/stream` | SSE 기반 기사 생성 진행 스트림 + 저장 |

`POST /articles/generate` 요청:

```json
{
  "press_release_ids": ["kcc_20260421_0eaf3e36"],
  "related_article_ids": ["KCC_20260421_abcd1234_001"],
  "created_by": "김홍근",
  "model_key": "claude-sonnet-4-6",
  "article_style": "mediaus",
  "article_tone": "mz"
}
```

응답에는 생성 결과와 `article_id`가 함께 들어갑니다.

LLM provider:

- `LLM_PROVIDER=openai | anthropic | bedrock`
- Bedrock 사용 시 `BEDROCK_REGION`, `BEDROCK_DEFAULT_MODEL_KEY`, `BEDROCK_MODEL_CATALOG_JSON`을 설정합니다.
- `ap-northeast-2`에서는 카탈로그의 실제 `model_id`에 inference profile ID를 넣습니다. 예: `global.anthropic.claude-sonnet-4-6`, `apac.amazon.nova-lite-v1:0`
- Claude 계열은 계정 최초 1회 Anthropic use case details 제출이 끝나야 호출됩니다.
- 모델 선택 UI는 `GET /llm/models`에서 허용목록만 받아 사용하며, 기본 모델은 `claude-sonnet-4-6`입니다.
- Opus 계열은 계정에서 ConverseStream 호출이 실제로 허용된 뒤 `BEDROCK_MODEL_CATALOG_JSON`에 추가합니다.
- 기사 스타일은 `ARTICLE_STYLE=default | mediaus`를 기본값으로 두고 요청별 `article_style`로 덮어쓸 수 있습니다.
- 말투는 요청별 `article_tone`으로 지정합니다. 허용값은 `default`, `professional`, `friendly`, `direct`, `distinctive`, `efficient`, `critical`, `mz`입니다.
- 컨테이너는 표준 AWS credential chain을 사용하므로 로컬은 `AWS_*` 환경변수, EC2는 IAM role 기준으로 연결합니다.
- 프론트는 `/articles/generate/stream`을 사용해 문서 준비, 사실 추출, 초안 작성, 저장 단계를 표시하고 초안 토큰을 실시간으로 렌더링합니다.

## 운영 메모

- 기본 수집 주기: `CRAWLER_INTERVAL_MINUTES=10`
- outbox 경로: `CRAWLER_OUTBOX_DIR=/shared/outbox`
- 처리 완료 경로: `CRAWLER_PROCESSED_DIR=/shared/processed`
- ingest polling: `INGEST_POLL_SECONDS=15`
- 기본 compose는 EC2 로컬 PostgreSQL 기준입니다. 추후 RDS 전환은 `PG_*` 환경변수만 바꾸면 됩니다.
- `INGEST_USE_CONTEXT=0`은 로컬 데모 기본값입니다. contextual retrieval까지 켜려면 `1`로 바꾸고 OpenAI 키를 설정합니다.
