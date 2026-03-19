# 공식 문서 기반 속보 콘텐츠 자동 생성 AI - 프로젝트 기획 및 구현 가이드

> 빅데이터 캡스톤디자인 과제 | 언론사 '미디어스' 협업 | RAG 기반 속보기사 생성 보조 시스템

---

## 0. 빠른 시작

### 로컬 실행 (풀스택 통합 개발)

**백엔드 (FastAPI)**

```bash
cd News
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

API 문서: [http://localhost:8000/docs](http://localhost:8000/docs)

**프론트엔드 (React + Vite)**

```bash
cd News/frontend
npm install
npm run dev
```

브라우저: [http://localhost:5173](http://localhost:5173)

### 프로젝트 구조

```
News/
├── backend/           # FastAPI (풀스택 담당)
│   ├── main.py
│   ├── routers/
│   ├── adapters/     # 추상화 레이어 (크롤러, RAG, LLM - 담당 확정 시 구현체 교체)
│   └── data/
├── frontend/         # React + Vite (design 폴더 기반 UI)
│   └── src/
│       ├── components/
│       │   ├── LeftPanel.tsx      # 좌측 358px 녹색 네비 (3단계)
│       │   ├── DataSelection.tsx  # 보도자료 선택
│       │   ├── InfoSearch.tsx     # 참고 기사 선택
│       │   └── AIGeneration.tsx   # 기사 편집기 (AI 생성, 출처 아이콘)
│       └── App.tsx
└── PROJECT_CONTEXT.md
```

---

## 1. 배포

### Docker

```bash
cd News
docker compose up --build
```

- 백엔드: [http://localhost:8000](http://localhost:8000)
- 프론트엔드: [http://localhost:5173](http://localhost:5173)

**코드 변경 후**: 이미지가 빌드 시점에 고정되므로 변경 사항을 보려면 `docker compose up --build`로 다시 빌드 후 실행해야 한다.

**참고**: Docker 사용 시 `npm run dev`를 실행하지 말 것. 포트 5173 충돌 시 Docker 대신 로컬 Vite가 응답할 수 있음.

### 인프라 (AWS, 상세 미정)

- **플랫폼**: AWS 예정 (EC2, ECS, Lambda, RDS 등 추후 결정)
- **배포 방식**: Docker 기반. 인프라 구성 확정 시 반영 예정

---

## Part 1. 프로젝트 개요

### 1.1 과제 개요


| 구분        | 내용                           |
| --------- | ---------------------------- |
| **과제명**   | 공식 문서 기반 속보 콘텐츠 자동 생성 AI     |
| **협업 기업** | 온라인 언론사 '미디어스'               |
| **핵심 가치** | 루틴 기사 자동화 → 기자가 특종/심층 보도에 집중 |


### 1.2 과제 목표

공식 보도자료가 입력되면

- 관련 과거 기사와 정책 문서를 **자동으로 검색**하고
- 그 정보를 활용하여
- **배경 설명이 포함된 속보기사 초안**을 생성하는

**AI 기자 보조 시스템**을 개발한다.

이 시스템은 단순 기사 생성이 아니라

- 문서 검색 (RAG)
- 사실 기반 기사 생성
- 근거 기반 기사 작성

을 목표로 한다.

### 1.3 해결하려는 문제

- **다부처 공식 문서 실시간 파악 어려움**: 방통위, 국회, 방송사 등 여러 소스에서 수시로 보도자료 발표
- **핵심 vs 부수 내용 구분 어려움**: 빠른 판단 필요
- **요약이 아닌 콘텐츠 형태 필요**: 제목·리드·본문 구조의 기사 초안

**기자가 속보기사를 작성할 때 실제로 하는 일**

1. 보도자료 확인
2. 핵심 내용 정리
3. 과거 정책 확인
4. 관련 기사 검색
5. 배경 설명 추가
6. 기사 작성

이 과정 중 **특히 시간이 오래 걸리는 것**은 과거 기사와 정책을 찾는 과정이다. 본 과제는 이 과정을 **자동화**하는 시스템을 만드는 것이다.

### 1.4 개념 정리: 뉴스기사 vs 보도자료


| 구분      | **보도자료 (Press Release)** | **뉴스기사 (News Article)** |
| ------- | ------------------------ | ----------------------- |
| **작성자** | 기관·기업·정부 등               | 언론사 기자                  |
| **목적**  | 자기 입장·정책·사실 전달           | 독자에게 사실·맥락 전달           |
| **성격**  | 일방적 발표, 홍보·설명 중심         | 검증·취재·해석 포함             |
| **출처**  | 방통위, 국회, 방송사, 언론노조 등     | 미디어스, 조선일보, 한겨레 등       |
| **형식**  | 공문·성명·논평 형태              | 제목·리드·본문 구조             |


**예시**

- **보도자료**: 방통위가 "소상공인 점포 정보 전송 서비스 2년 연장" 발표
- **뉴스기사**: 기자가 그 내용을 취재·해석해 "방통위, 소상공인 점포 정보 전송 서비스 2년 연장" 기사로 작성

### 1.5 속보 기사 정보 수집 소스

속보는 **보도자료**를 주로 사용한다.

```
속보 정보 흐름
┌─────────────────────────────────────────────────────────────┐
│  정보원 (1차)          →    언론사 (2차)                     │
│  보도자료·성명·발표    →    기자가 취재·기사화               │
└─────────────────────────────────────────────────────────────┘
```

**본 과제에서 수집하는 소스**


| 소스              | 성격            | 내용         |
| --------------- | ------------- | ---------- |
| **방송통신위원회**     | 정부부처          | 정책·규제·보도자료 |
| **국회 동향 (NSP)** | 국회도서관         | 정책·입법 동향   |
| **방송사 보도자료**    | MBC, SBS, KBS | 입장·정책 대응   |
| **언론노조 성명**     | 노조            | 성명·논평·보도자료 |


**RAG 시스템에서의 역할**

- **벡터 DB**: 과거 **뉴스기사 + 보도자료**를 함께 저장
- **신규 보도자료**: 방통위·국회 등에서 새로 나온 **보도자료**
- **RAG 검색**: 새 보도자료와 관련된 **과거 기사·보도자료**를 찾아서 맥락 제공
- **기사 생성**: 새 보도자료 + 검색된 과거 자료를 기반으로 속보 초안 작성

**정리**: 속보의 **정보는 보도자료**에서 나오고, **과거 뉴스기사**는 RAG 검색 시 배경·맥락 설명용으로 활용된다.

---

## Part 2. 시스템 핵심 아이디어 (RAG)

### 2.1 핵심 원칙

**AI에게 바로 기사를 쓰게 하지 않는다.**

먼저

- 과거 문서를 **검색**하고
- 그 정보를 **근거**로 기사 생성

을 수행한다. 이 구조를 **RAG (Retrieval Augmented Generation)** 로 구현한다.

### 2.2 시스템 전체 구조

```
뉴스/보도자료 크롤링
        ↓
문서 저장
        ↓
문서 청킹
        ↓
임베딩 생성
        ↓
벡터DB 저장
        ↓
새 보도자료 입력
        ↓
벡터DB 검색 (RAG)
        ↓
관련 문서 추출
        ↓
LLM 기사 생성
        ↓
속보기사 출력
```

### 2.3 RAG 시스템 동작 원리

#### 1. 과거 문서 저장

시스템은 매일

- 뉴스 기사
- 보도자료

를 크롤링하여 저장한다.

**예**: 2023 방송 규제 개편 기사, 언론노조 성명, 방송사 입장 기사

#### 2. 문서 벡터화

문서를 작은 단위로 분해한다.

- chunk_1, chunk_2, chunk_3
- 각 문장은 벡터로 변환된다.
- 벡터DB에 저장한다.

#### 3. 새로운 보도자료 입력

예: 방통위가 방송 규제 완화 정책을 발표했다. → 이 문서도 벡터로 변환된다.

#### 4. 벡터DB 검색

오늘 보도자료 벡터와 벡터DB에 저장된 문서를 비교하여 가장 유사한 문서를 찾는다.

예: 2023 방송 규제 개편 기사, 방송사 입장 기사

#### 5. LLM 기사 생성

- **LLM 입력**: 오늘 보도자료 + 검색된 과거 기사
- **LLM 출력**: 속보기사 + 배경 설명

### 2.4 기사 생성 예시


| 구분                 | 내용                                                               |
| ------------------ | ---------------------------------------------------------------- |
| **입력 (오늘 보도자료)**   | 방통위가 방송 규제 완화 정책을 발표했다.                                          |
| **입력 (검색된 과거 기사)** | 2023년 방송 규제 개편 정책                                                |
| **출력 기사**          | 방송통신위원회가 방송 규제 완화 정책을 발표했다. 이번 정책은 2023년 방송 규제 개편안의 후속 조치로 평가된다. |


---

## Part 3. 수집 대상 소스 (크롤링 대상)

### 1. 방송통신위원회 보도자료


| 항목         | 내용                                                                                                                     |
| ---------- | ---------------------------------------------------------------------------------------------------------------------- |
| **목록 페이지** | [https://www.kcc.go.kr/user.do?boardId=1113&page=A05030000](https://www.kcc.go.kr/user.do?boardId=1113&page=A05030000) |
| **페이지 구조** | 게시판 구조, 각 행에 제목/날짜/상세페이지 링크                                                                                            |
| **상세 페이지** | 본문 텍스트, 첨부파일(PDF/HWP)                                                                                                  |
| **수집 필드**  | source="KCC", title, date, detail_url, content_text, attachments[]                                                     |


### 2. 국회 동향 (NSP – 국회도서관)


| 항목        | 내용                                                                                           |
| --------- | -------------------------------------------------------------------------------------------- |
| **목록**    | [https://nsp.nanet.go.kr/trend/latest/list.do](https://nsp.nanet.go.kr/trend/latest/list.do) |
| **특징**    | 정책/국회 동향 요약 형태, HTML 텍스트 중심, PDF 첨부는 많지 않음                                                   |
| **수집 필드** | source="National Assembly", title, date, summary, detail_url, content_text                   |


### 3. 방송사 보도자료


| 방송사 | URL                                                                                            |
| --- | ---------------------------------------------------------------------------------------------- |
| MBC | [https://with.mbc.co.kr/pr/press/index.html](https://with.mbc.co.kr/pr/press/index.html)       |
| SBS | [https://sbspr.sbs.co.kr/weekly/renew_bodo.jsp](https://sbspr.sbs.co.kr/weekly/renew_bodo.jsp) |
| KBS | [https://mylovekbs.kbs.co.kr/data/](https://mylovekbs.kbs.co.kr/data/)                         |


**특징**: 프로그램 홍보, 조직 입장, 정책 대응, 대부분 HTML

**수집 필드**: source="Broadcast", company, title, date, detail_url, content_text

**참고**: SBS 콘텐츠 수집 약관 확인 필요

### 4. 언론노조 성명


| 항목        | 내용                                                                                                         |
| --------- | ---------------------------------------------------------------------------------------------------------- |
| **URL**   | [https://media.nodong.org/bbs/list.html?table=bbs_48](https://media.nodong.org/bbs/list.html?table=bbs_48) |
| **특징**    | 성명, 논평, 보도자료, 언론 환경 관련 기사 생성에 매우 유용                                                                        |
| **수집 필드** | source="Media Union", title, date, detail_url, content_text                                                |


**크롤링 시 필수**: 원문 링크 포함, 10분 주기 모니터링 (과제 요구)

---

## Part 4. 구현 파이프라인 (8단계 상세)

### 역할 분담


| 역할         | 담당    | 비고                                                         |
| ---------- | ----- | ---------------------------------------------------------- |
| **풀스택**    | 1명    | API + 프론트엔드 통합 개발 (완료)                                     |
| **크롤링**    | 다른 팀원 | 보도자료 수집, `PressReleaseProvider` 구현체 교체                     |
| **AI/전처리** | 다른 팀원 | 청킹, 임베딩, RAG, LLM. `RAGService`, `ArticleGenerator` 구현체 교체 |


### 전체 흐름

```
보도자료 크롤링 → 문서 청킹 → 임베딩 생성 → 벡터DB 저장
    → RAG 검색 → JSON 구조화 추출 → 기사 생성 → 사실 검증 → 속보기사 출력
```

### 보도자료 예시

방통위 '소상공인 점포 정보 전송 서비스' 2년 연장 보도자료  
(예: "가게 몇 시에 문 열어요" 안 물어봐도 된다)

---

### 1단계: 보도자료 크롤링

**목표**: 보도자료를 자동 수집

**예시 코드 개념**:

```python
import requests
from bs4 import BeautifulSoup

url = "방통위 보도자료 URL"
html = requests.get(url).text
soup = BeautifulSoup(html, "html.parser")
article = soup.get_text()
```

**결과**: 보도자료 전체 텍스트 + 원문 링크

---

### 2단계: 문서 청킹 (Chunking)

보도자료를 작은 의미 단위로 나눈다.

**예시**:


| chunk_id | text                                                  |
| -------- | ----------------------------------------------------- |
| chunk_1  | 가게 몇 시에 문 열어요 안 물어봐도 된다                               |
| chunk_2  | 소상공인 점포 정보 문자 서비스 2년 연장                               |
| chunk_3  | 방통위는 연 매출 10억 이하 소상공인 지원을 위해 사전동의 예외 허용을 2년 연장한다고 밝혔다 |
| chunk_4  | 이 정책은 2022년 코로나19 당시 도입됐다                             |
| chunk_5  | 현재 약 2만 명이 이용 중이다                                     |


**코드 예**:

```python
sentences = article.split(".")
chunks = []
for i, s in enumerate(sentences):
    chunks.append({
        "chunk_id": f"chunk_{i}",
        "text": s
    })
```

---

### 3단계: 임베딩 생성

각 chunk를 숫자 벡터로 변환한다. **목적**: 문장 의미 비교

```python
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
for chunk in chunks:
    chunk["embedding"] = model.encode(chunk["text"])
```

---

### 4단계: 벡터DB 저장

임베딩을 벡터DB에 저장한다. (예: Chroma DB)

```python
import chromadb

client = chromadb.Client()
collection = client.create_collection("media_docs")

for chunk in chunks:
    collection.add(
        documents=[chunk["text"]],
        embeddings=[chunk["embedding"]],
        ids=[chunk["chunk_id"]]
    )
```

모든 문장이 검색 가능한 지식이 된다.

---

### 5단계: RAG 검색

오늘 보도자료에서 핵심 내용을 query로 만들어 벡터DB를 검색한다.

**예시 query**: "소상공인 정책 연장"

```python
query_embedding = model.encode("소상공인 정책 연장")
results = collection.query(
    query_embeddings=[query_embedding],
    n_results=5
)
```

**검색 결과**: chunk_3 (정책 연장), chunk_4 (정책 도입), chunk_5 (이용자 수)

---

### 6단계: JSON 구조화 추출 (LLM 호출 1)

LLM에게 검색된 chunk를 주고 JSON으로 정리하라고 한다.

**JSON 스키마**:

```json
{
  "who": "",
  "policy": "",
  "decision": "",
  "target": "",
  "numbers": "",
  "origin": ""
}
```

**LLM 프롬프트**:

> 다음 텍스트에서 정보를 추출해라. JSON 형식으로 출력하라.
> 필드: who, policy, decision, target, numbers, origin
> 텍스트: [chunk_3, chunk_4, chunk_5]

**LLM 출력 예**:

```json
{
  "who": "방송통신위원회",
  "policy": "소상공인 점포 정보 전송 서비스",
  "decision": "사전동의 예외 허용 2년 연장",
  "target": "연 매출 10억 이하 소상공인",
  "numbers": "약 2만 명 이용",
  "origin": "2022년 코로나19 정책"
}
```

이 JSON이 **기사 재료**이다.

---

### 7단계: 기사 생성 (LLM 호출 2)

LLM에게 JSON을 주고 기사를 작성하라고 한다.

**프롬프트**:

> 다음 JSON 정보를 기반으로 속보기사를 작성하라. 추측하지 말고 JSON 정보만 사용하라.
> JSON: {...}

**LLM 출력 예**:

**제목**: 방통위, 소상공인 점포 정보 전송 서비스 2년 연장

**리드**: 방송통신위원회가 소상공인 점포 정보 전송 서비스의 사전동의 예외 허용을 2년 더 연장하기로 했다.

**본문 1**: 이번 조치는 연 매출 10억 원 이하 소상공인의 경제 회복을 지원하기 위한 것이다.

**본문 2**: 해당 정책은 코로나19 확산 당시인 2022년 처음 도입됐으며 현재 약 2만 명의 이용자가 사용하고 있다.

---

### 8단계: 사실 검증

JSON과 원문을 비교한다.

**검증 항목**:

- 숫자 확인
- 기관명 확인
- 날짜 확인

**오류가 있으면**: 경고 표시

---

## Part 5. 구현해야 할 핵심 기능 (5가지)

1. **보도자료 크롤링** – requests, BeautifulSoup
2. **문서 청킹** – chunk_id 생성
3. **임베딩 생성** – sentence-transformers
4. **벡터DB 검색 (RAG)** – query_vector 생성, top_k 검색
5. **LLM JSON 추출 + 기사 생성** – 2회 LLM 호출

### RAG 검색 모듈 핵심 코드 개념

```python
query_vector = embedding(today_document)
results = vectordb.search(
    vector=query_vector,
    top_k=5
)
```

---

## Part 6. 기술 스택


| 영역       | 추천                                                            | 비고     |
| -------- | ------------------------------------------------------------- | ------ |
| **언어**   | Python                                                        |        |
| **크롤링**  | requests, BeautifulSoup                                       |        |
| **임베딩**  | sentence-transformers (paraphrase-multilingual-MiniLM-L12-v2) | 다국어    |
| **벡터DB** | Chroma / Qdrant / FAISS                                       | 오픈소스   |
| **LLM**  | Claude API 1차 → 문제 없으면 Ollama(온프레미스) 전환                       | 교수님 권장 |


**LLM 전환 전략 (교수님 권장)**

1. **1차**: Claude API로 개발·검증
2. **다른 모듈에서 문제 발생 시**: LLM이 원인이 아니므로 해당 부분 먼저 해결
3. **전체 파이프라인 문제 없으면**: LLM을 온프레미스 Ollama로 교체

---

## Part 7. UI 설계 (사용자: 기자)

### 레이아웃: design 폴더 기반 (2026 적용)

- **좌측 네비 (358px, #4A5226)**: 속보 콘텐츠 자동 생성 시스템, 3단계 버튼(보도자료 → 참고 기사 → 기사 생성), 수집 소스 표
- **메인 영역 (3단계 스크롤)**:
  1. **보도자료**: 최신 보도자료 검색·선택, 시작일/종료일 캘린더, NEW 배지(반짝 애니메이션), 마지막 업데이트 표시
  2. **참고 기사**: 보도자료 선택 시 관련 참고 기사 자동 표시, 복수 선택 가능 (참고 기사 하단 "기사 생성하기" 버튼 없음)
  3. **기사 편집기**: AI 기사 생성 버튼, 제목/리드/본문 편집, **본문 출처 아이콘**(호버 시 크롤링 데이터 세부·원문 링크 툴팁), 저장(.md 다운로드), 발행(비활성화)

### 기자 워크플로우

1. 보도자료 선택 → 관련 참고 기사 자동 표시
2. 참고 기사 확인·선택 (선택 사항)
3. 좌측 "03 기사 생성" 클릭 → 기사 편집기로 이동
4. AI 기사 생성 → 본문에 출처 아이콘 표시, 호버 시 출처 세부 확인
5. 수정 후 저장(마크다운 다운로드)

### 저장/발행 동작


| 버튼     | 동작                     |
| ------ | ---------------------- |
| **저장** | 제목+리드+본문을 .md 파일로 다운로드 |
| **발행** | 비활성화 (CMS 연동 예정)       |


### 디자인 원칙 (당근 참고)

- 미니멀, 카드 기반, 명확한 위계, CTA 강조
- about.daangn.com, 블로그 스타일 참고

---

## Part 8. 개발 단계 (Phase)


| Phase       | 내용                                 |
| ----------- | ---------------------------------- |
| **Phase 1** | 크롤러 개발 (소상공인 점포 전송 서비스 보도자료 확인 선행) |
| **Phase 2** | 문서 저장 / 청킹                         |
| **Phase 3** | 벡터DB 구축                            |
| **Phase 4** | RAG 검색                             |
| **Phase 5** | 기사 생성 시스템                          |
| **Phase 6** | UI 설계 및 흐름도 확정                     |


---

## Part 9. 최종 산출물

1. 문서 수집 시스템
2. 벡터DB 구축
3. RAG 검색 시스템
4. 속보기사 생성 기능
5. 기사 생성 데모 시스템

---

## Part 10. 다음 할 일 (회의 기준)

- **소상공인 점포 전송 서비스** 보도자료 확인
- **오픈소스 LLM** 성능 테스트 계획 수립
- **UI 설계 및 흐름도** 결정
- **SBS 콘텐츠 수집 약관** 확인 (방송사 크롤링 시)
- 개발자 미팅 스케줄 및 중간 체크 포인트 설정

---

## Part 11. 옵션 기능 (시간 여유 시)

- 비정형 문서 벡터 DB화
- 표/그래프 자동 생성
- 정책 비평 모니터링 기관 추가

---

## Part 12. 산출물 체크리스트

- 보도자료 자동 수집 시스템
- 벡터DB 구축 (RAG)
- JSON 구조화 추출 + 기사 생성
- 사실 검증 로직
- 기자용 편집 UI 데모
- 3초 내 기사 생성 목표 달성 여부

---

## 부록: 팀 역할 추상화

크롤링, AI/전처리 담당이 미정이므로 **코드는 추상화**하여 작성한다.

- **PressReleaseProvider**: 보도자료 목록 제공 (크롤러 또는 목업)
- **RAGService**: RAG 검색 (미구현 시 목업)
- **ArticleGenerator**: 기사 생성 (LLM 연동 전 목업)

담당 확정 시 구현체만 교체하면 되도록 `backend/adapters/`에 Protocol 정의.

---

## 부록: 크롤링 데이터 연동 가이드

크롤링 담당 팀원이 수집한 보도자료를 시스템에 연동하는 방법.

### 1. 연동 위치

**파일**: `backend/deps.py`  
**어댑터**: `backend/adapters/providers.py` (PressReleaseProvider 인터페이스)

현재 `MockPressReleaseProvider`가 목업 데이터를 반환한다. 크롤러 구현체로 교체하면 된다.

### 2. 구현체 교체 절차

1. `backend/adapters/`에 새 구현체 생성 (예: `crawler_provider.py`)
2. `PressReleaseProvider` Protocol을 준수

```python
class CrawlerPressReleaseProvider:
    def get_releases(self) -> list[dict]:
        # 크롤링 결과 반환
        return [...]
```

1. `backend/deps.py`에서 `get_press_release_provider`가 새 구현체를 반환하도록 수정

```python
from backend.adapters.crawler_provider import CrawlerPressReleaseProvider

_provider = CrawlerPressReleaseProvider()
```

### 3. API 계약 (반드시 준수)


| 필드         | 타입      | 필수  | 설명                            |
| ---------- | ------- | --- | ----------------------------- |
| id         | string  | O   | 보도자료 고유 ID                    |
| title      | string  | O   | 제목                            |
| source     | string  | O   | 출처 (KCC, National Assembly 등) |
| date       | string  | O   | 날짜 (YYYY-MM-DD)               |
| summary    | string  | X   | 요약                            |
| detail_url | string  | O   | 원문 링크                         |
| is_new     | boolean | X   | 신규 표시 (UI NEW 배지용)              |


### 4. 상세 원문 (content_text)

`GET /press-releases/{release_id}` 호출 시 `content_text`가 필요하다. 크롤러가 DB나 파일에 저장한 본문을 `backend/routers/press_releases.py`의 `get_press_release_detail`에서 조회하도록 수정해야 한다. 현재는 `backend/data/mock.py`의 `MOCK_CONTENT`를 사용 중.

---

## 부록: AI/RAG 연동 가이드

AI 담당 팀원이 RAG 검색·기사 생성을 연동하는 방법.

### 1. 연동 위치


| 기능               | API                                     | 관련 어댑터                  |
| ---------------- | --------------------------------------- | ----------------------- |
| 참고 기사 + 기사 핵심 정보 | `GET /press-releases/related?ids=1,2,3` | RAGService (미연동, 목업 사용) |
| 기사 생성            | `POST /articles/generate`               | ArticleGenerator (미연동)  |


### 2. 참고 기사 API 연동

**파일**: `backend/routers/press_releases.py`의 `get_related_articles_batch`

현재 `MOCK_RELATED`, `MOCK_JSON`을 사용. RAG 검색 결과로 교체하려면:

1. `RAGService`, `ArticleGenerator` 구현체 작성
2. `get_related_articles_batch`에서 RAGService.search 호출
3. 검색된 문서를 `RelatedArticle` 형식으로 변환

**RelatedArticle 스키마**:


| 필드                   | 타입     | 필수  | 설명                  |
| -------------------- | ------ | --- | ------------------- |
| id                   | string | O   | 참고 기사 ID            |
| title                | string | O   | 제목                  |
| source               | string | O   | 출처 (연합뉴스 등)         |
| date                 | string | O   | 날짜                  |
| source_release_id    | string | X   | 연관 보도자료 ID          |
| source_release_title | string | X   | 연관 보도자료 제목 (배지 표시용) |


### 3. 기사 생성 API 연동

**파일**: `backend/routers/articles.py`의 `generate_article`

**요청 본문** (프론트엔드에서 전송):

```json
{
  "press_release_ids": ["1", "2"],
  "related_article_ids": ["r1-1", "r2-1"]
}
```

**응답 형식** (프론트엔드가 기대):

```json
{
  "title": "방통위, 소상공인 점포 정보 전송 서비스 2년 연장",
  "lead": "방송통신위원회가 소상공인 점포 정보 전송 서비스의 사전동의 예외 허용을 2년 더 연장하기로 했다.",
  "body": "이번 조치는 연 매출 10억 원 이하 소상공인의 경제 회복을 지원하기 위한 것이다.[1]\n\n해당 정책은 코로나19 확산 당시인 2022년 처음 도입됐으며 현재 약 2만 명의 이용자가 사용하고 있다.[1]",
  "citations": {
    "1": {
      "category": "방송통신위원회 보도자료",
      "title": "소상공인 점포 정보 전송 서비스의 사전동의 예외 허용 기간 연장 발표문",
      "date": "2026-03-19",
      "url": "https://..."
    }
  }
}
```

- **body**: 문장 끝에 `[1]`, `[2]` 출처 마커 포함. UI에서 녹색 정보 아이콘으로 렌더, 호버 시 툴팁 표시.
- **citations**: 출처 ID별 메타데이터 (category, title, date, url). 보도자료·참고기사 선택에 따라 구성.

AI 담당은 `ArticleGenerator.generate`를 구현해 RAG 검색 결과 + 참고 기사 + 보도자료를 LLM에 전달하고, 위 JSON을 반환하면 된다.

### 4. JSON 구조화 (기사 핵심 정보)

Part 4 6단계의 JSON 스키마(who, policy, decision, target, numbers, origin)는 RAG 검색 시 LLM 1단계 추출 결과로 사용된다. `GET /press-releases/related?ids=...` 응답의 `json` 필드에 포함된다. UI에서 별도 표시는 제거했으나, AI 파이프라인 내부에서 기사 생성 재료로 활용 가능.