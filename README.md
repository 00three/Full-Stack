<div align="center">

# 📰 속보생성 보조시스템

**보도자료 기반 RAG 속보기사 자동 생성 플랫폼**

기자가 보도자료를 선택하면, 관련 기사를 검색하고 인용까지 자동으로 묶어 한국어 속보 초안을 만들어주는 시스템입니다.

<br/>

![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.135-009688?style=for-the-badge&logo=fastapi&logoColor=white)
![Next.js](https://img.shields.io/badge/Next.js-15-000000?style=for-the-badge&logo=nextdotjs&logoColor=white)
![React](https://img.shields.io/badge/React-19-61DAFB?style=for-the-badge&logo=react&logoColor=black)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-17-4169E1?style=for-the-badge&logo=postgresql&logoColor=white)
![pgvector](https://img.shields.io/badge/pgvector-0.7-8E44AD?style=for-the-badge&logo=postgresql&logoColor=white)
![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4o--mini-10A37F?style=for-the-badge&logo=openai&logoColor=white)
![Tailwind](https://img.shields.io/badge/Tailwind-4-06B6D4?style=for-the-badge&logo=tailwindcss&logoColor=white)

</div>

---

## ✨ 핵심 기능

| | |
|---|---|
| 🔍 **하이브리드 검색** | 의미 기반(임베딩) + 키워드 검색을 RRF로 결합하고, 시간 가중치로 최신성까지 반영해 관련 기사를 추천 |
| 📝 **3단계 LLM 체인** | 핵심 팩트 추출 → 기사 생성 → 사실 검증 단계로 분리하여 환각 최소화 |
| 🔗 **출처 추적 인용** | 본문에 `[1]`, `[2]` 인용 마커 자동 삽입, 호버 시 원문 링크까지 확인 가능 |
| ⚡ **단계별 워크플로우** | 보도자료 선택 → 관련 기사 → 생성 검토 → AI 에디터까지 직관적 4-Step UI |

---

## 🚀 빠른 시작

> [!NOTE]
> 사전 준비: PostgreSQL 17 + pgvector, Python 3.11, Node.js 20+, OpenAI API 키

### 1) 환경 변수 설정

루트에 `.env` 파일을 만드세요.

```env
PG_HOST=localhost
PG_PORT=5432
PG_DATABASE=rag_db
PG_USER=postgres
PG_PASSWORD=postgres
OPENAI_API_KEY=sk-...
```

### 2) 백엔드 실행

```bash
conda create -n rag python=3.11 -y && conda activate rag
pip install -r backend/requirements.txt -r rag/requirements.txt
uvicorn backend.main:app --reload --port 8000
```

> [!TIP]
> 데이터 없이 UI만 보고 싶다면 `USE_MOCK=1 uvicorn ...` 으로 mock 모드 사용 가능

API 문서: http://localhost:8000/docs

### 3) 프론트엔드 실행

```bash
cd frontend
npm install
npm run dev
```

브라우저: http://localhost:3000

---

## 🏗 시스템 아키텍처

```
┌──────────────┐      ┌──────────────────────────────────┐      ┌─────────────────┐
│              │      │  SERVER (AWS EC2)                │      │                 │
│   Frontend   │◄────►│  ┌────────────────────────────┐  │◄────►│  AWS RDS        │
│   (Next.js)  │ HTTPS│  │  Docker Compose            │  │      │  PostgreSQL     │
│              │ JSON │  │  ├ FastAPI  (API)          │  │      │  + pgvector     │
│  4-Step UI   │      │  │  ├ RAG 서비스 (Hybrid)     │  │      │                 │
│              │      │  │  └ 임베더 (S-Transformers) │  │      └─────────────────┘
└──────────────┘      │  └────────────────────────────┘  │
                      └──────────────┬───────────────────┘
                                     │ AI 요청 / 응답
                                     ▼
                              ┌─────────────────┐
                              │  OpenAI API     │
                              │  GPT-4o-mini    │
                              └─────────────────┘
```

오프라인 데이터 흐름: `웹 크롤러 → JSONL → 8단계 Ingest 파이프라인 → RDS`

> 상세 다이어그램은 `architecture.drawio` 참고

---

## 📂 프로젝트 구조

```
Full-Stack/
├─ backend/              FastAPI 서버
│  ├─ main.py            앱 진입점 + CORS
│  ├─ routers/           press-releases / articles 라우터
│  ├─ adapters/          DB · RAG · LLM 어댑터 (mock/실DB 토글)
│  └─ deps.py            의존성 주입 (USE_MOCK 환경변수)
│
├─ frontend/             Next.js 15 + React 19
│  ├─ app/               App Router 페이지
│  │  └─ components/     NewsDashboard, BodyWithCitations 등
│  └─ lib/api.ts         RAG API 클라이언트
│
├─ rag/                  RAG 파이프라인
│  ├─ ingest.py          8단계 ingest 오케스트레이션
│  ├─ chunker.py         청킹
│  ├─ contextualizer.py  Contextual Retrieval
│  ├─ embedder.py        Sentence-Transformers
│  ├─ search.py          Hybrid Search + RRF + 시간 재순위
│  └─ llm.py             3단계 LLM 체인
│
├─ docker-compose.yml
└─ .env.example
```

---

## 🌐 API 엔드포인트

| Method | 경로 | 설명 |
|--------|------|------|
| `GET` | `/press-releases?q=` | 보도자료 목록 (검색어 옵션) |
| `GET` | `/press-releases/{id}` | 보도자료 상세 |
| `GET` | `/press-releases/related?ids=` | 보도자료별 관련 기사 + 핵심 JSON |
| `POST` | `/articles/generate` | 기사 본문 + 인용 자동 생성 |

자세한 응답 스키마는 `/docs` (Swagger UI)에서 확인할 수 있습니다.

---

## 🔧 기술 스택

<table>
<tr>
<td><b>Frontend</b></td>
<td>Next.js 15, React 19, TypeScript, Tailwind CSS, Framer Motion</td>
</tr>
<tr>
<td><b>Backend</b></td>
<td>FastAPI, Uvicorn, Pydantic, psycopg2</td>
</tr>
<tr>
<td><b>RAG · ML</b></td>
<td>OpenAI GPT-4o-mini, Sentence-Transformers, Hybrid Search (Dense + Keyword + RRF)</td>
</tr>
<tr>
<td><b>Database</b></td>
<td>PostgreSQL 17, pgvector</td>
</tr>
<tr>
<td><b>Infra</b></td>
<td>AWS EC2, AWS RDS, AWS ECR, Docker Compose, GitHub Actions</td>
</tr>
</table>

---

## 📚 더 읽기

- [`PROJECT_CONTEXT.md`](./PROJECT_CONTEXT.md) — 프로젝트 배경 및 의사결정 맥락
- [`RAG_속보기사_생성_보조시스템_전체설계문서.md`](./RAG_속보기사_생성_보조시스템_전체설계문서.md) — 전체 설계 문서
- [`rag/팀원_가이드_전처리.md`](./rag/팀원_가이드_전처리.md) — 전처리 단계 가이드
- [`rag/팀원_가이드_크롤링.md`](./rag/팀원_가이드_크롤링.md) — 크롤링 단계 가이드

---

## 👥 팀

빅데이터 캡스톤디자인 · 언론사 '미디어스' 협업 프로젝트

> [!IMPORTANT]
> 본 시스템은 기자의 속보 작성을 **보조**하는 도구로, 최종 기사 발행 전 반드시 사람의 검토를 거치도록 설계되었습니다.
