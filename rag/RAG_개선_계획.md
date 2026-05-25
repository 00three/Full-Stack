# RAG 성능 개선 계획

> 작성일: 2026-05-24
> 대상 시스템: `Full-Stack/rag/` + `backend/adapters/article_generator.py`
> 목적: 현재 RAG 파이프라인의 약점을 진단하고, 영향도/비용 기준으로 우선순위화된 개선안 정리

---

## 1. 현재 시스템 진단 — 직접 확인한 문제점

코드를 직접 읽어 발견한 구체적 약점들. (가설이 아니라 코드 근거 있음)

### A. 보도자료 vs 참고기사의 비대칭이 과도하다 (가장 시급)

`generate_article`이 받는 chunks 배열에서 `index=0`은 보도자료, 나머지는 참고기사로 분류되어 글자수가 잘립니다 ([llm.py:659-667](llm.py)).

| 단계 | 보도자료(index=0) | 참고기사(index≥1) | 비율 |
|---|---|---|---|
| extract (JSON 추출) | 1800자 | **700자** | 보도자료 2.6배 |
| generate (기사 생성) | 4200자 | **1200자** | 보도자료 3.5배 |
| 참고기사 최대 개수 | — | **5개** ([article_generator.py:192](../backend/adapters/article_generator.py)) | |

추가로 시스템 프롬프트 [llm.py:319-326](llm.py)에 명시:
- *"Center the article on the core facts from the extracted JSON"*
- *"Enrich with background, context from the reference sources"*

→ **참고기사는 구조적으로 "배경 양념" 역할로 격하**됨. 기자가 핵심 자료라고 골라도 본문에 들어갈 여지가 적음.

### B. BGE-M3 sparse vector 미사용 (공짜로 검색 품질 ↑)

[embedder.py:90-97](embedder.py):
```python
out = self._model.encode(
    texts,
    return_dense=True,
    return_sparse=False,   # ← 꺼져있음
    return_colbert_vecs=False,
)
```

BGE-M3는 dense + sparse + colbert 세 종류를 **한 번의 forward pass로** 같이 출력하는 모델입니다. 지금 sparse를 안 쓰고 있는데, sparse 벡터는 정확한 단어 매칭(고유명사, 숫자, 약어)에 강해서 한국 보도자료 도메인에 잘 맞습니다.

→ **현재 keyword 검색을 PostgreSQL `tsvector('simple')`로 하고 있는데, BGE-M3 sparse가 이걸 대체하거나 보강 가능.** GPU 추가 비용 0.

### C. tsvector 키워드 검색이 사실상 죽어있을 가능성이 매우 높음 (⚠️ 시급)

[search.py:54-61](search.py)의 keyword_search는 세 가지 함정이 겹쳐서 **실제로는 거의 빈 결과만 반환**할 가능성이 큼.

**함정 ①: `plainto_tsquery`는 AND로 묶음**
```sql
WHERE to_tsvector('simple', d.full_text) @@ plainto_tsquery('simple', %s)
```
입력 텍스트의 모든 토큰을 AND 결합. 쿼리에 토큰 10개면 chunk가 10개 단어를 **모두** 가져야 매치.

**함정 ②: `'simple'` 컨피그 + 한국어 = 조사 붙은 채로 토큰화**
- "방송통신위원회**는**" ≠ "방송통신위원회"
- "허용**을**" ≠ "허용"
- "방통위" ≠ "방송통신위원회"

조사 차이로 같은 단어가 다르게 취급. 한국어 형태소 분석기(kiwi, mecab) 미적용.

**함정 ③: 쿼리가 보통 너무 김**
이 시스템의 query_text는 보도자료 본문(수백~수천 자, 고유 토큰 50~100개). AND 결합되면 매치 chunk 거의 0건.

**결과**: keyword_search가 빈 리스트만 반환 → RRF 합산이 사실상 dense-only로 동작 → `keyword_weight=0.5`는 낭비. 보도자료처럼 **고유명사·기관명·정책명·금액·날짜**가 핵심인 도메인에서 키워드 검색이 죽으면 손실이 큼.

**검증 방법** (dev DB에서 즉시 확인):
```sql
SELECT count(*)
FROM documents d
WHERE to_tsvector('simple', d.full_text)
   @@ plainto_tsquery('simple', '<보도자료 본문 또는 제목>');
-- 0~5 정도면 키워드 검색은 사실상 죽은 코드 확정
```

### D. document_kind 필터링이 검색에 안 들어감

[search.py:30](search.py)에서 `document_kind`를 SELECT만 하고 WHERE에는 안 씁니다. 그래서 기자가 "방통위 정책 발표" 보도자료를 쿼리로 던졌을 때, 검색 결과에 다른 방통위 보도자료의 chunk(`press_release`)와 외부 참고기사(`reference_article`)가 섞입니다.

→ 의도된 설계지만 **튜닝 옵션을 안 제공**하는 게 문제. UI에서 "참고기사만" / "전체" 토글이 있으면 좋음.

### E. Contextual prefix 생성 비용 비효율

[contextualizer.py:88-100](contextualizer.py):
```python
client = OpenAI(api_key=llm_config.api_key)
resp = client.chat.completions.create(
    model="gpt-4o-mini",   # ← 모델 하드코딩
    ...
)
```

문제:
1. **모델 하드코딩** — Bedrock Haiku 4.5나 Nova-lite로 못 바꿈
2. **chunk마다 LLM 1콜** — 4000자 문서가 10 chunk면 10콜. 같은 document 전체를 매번 다시 보냄(`max_doc_chars=8000`).
3. **document 전체를 매 콜마다 입력 토큰으로 소모** — input 토큰 낭비가 큼.

→ 같은 doc의 모든 chunk를 1콜로 batch 처리하거나, doc 1회 요약 후 chunk별로는 위치 정보만 붙이는 방식으로 5-10배 절감 가능.

### F. 청킹 파라미터가 한국어 보도자료에 비최적화

| 항목 | 현재 | 이슈 |
|---|---|---|
| `chunk_size` | 400자 | 한국어 보도자료 한 단락 ~ 한 단락 반 분량. 사실 단위가 chunk 경계에서 끊김 |
| `chunk_overlap` | 100자 | OK |
| `separators` | `["\n\n", "\n", ". ", " "]` | 한국어 종결어미 미적용. "다. " "요. " 등으로 끊는 게 더 자연스러움 |
| 보도자료/PDF 동일 청크 | 둘 다 400 | PDF는 보고서 형식이라 더 큰 청크가 유리할 수 있음 |

[팀원_가이드_전처리.md:75](팀원_가이드_전처리.md)에 "200/400/600 실험 예정"으로 명시됨 → 미완료.

### G. meta_prefix를 임베딩에서 제외한 부작용

[embedder.py:42-44](embedder.py)에 *"source 토큰이 강하게 학습되어 cross-source 검색이 막힘"* 으로 제외. 의도는 이해되지만:
- date도 같이 제외 → **시간 가중치를 임베딩이 모름**. 최신 정책 쿼리에 오래된 chunk가 잡힐 수 있음
- date만 부분 포함하거나, source는 별도 부스팅 컬럼으로 분리하는 것도 고려

### H. 중복 임계값 0.95가 공격적일 가능성

[ingest.py:275](ingest.py): `DUP_THRESHOLD = 0.95`. 코사인 0.95는 거의 같은 문장이지만, BGE-M3가 표현 약간 다른 문장도 0.95+로 잡을 수 있음. 그러면 미묘하게 다른 정보가 병합되어 정보 손실.

→ 0.97로 올려서 비교 가치 있음.

### I. citation 마커 강제하지만 분포 검증 없음

[llm.py:757](llm.py): *"End every body paragraph with at least one citation marker like [1] or [2]"*. 그런데 후처리에서 **모든 단락이 [1](보도자료)만 가리키는지** 검증하지 않습니다. 참고기사 [2]~[N]이 실제로 인용됐는지 확인 필요.

### J. 평가 인프라가 전무

- self-retrieval 스크립트 X
- 골든셋 X
- 정량 metric X
- A/B 비교 기록 X

→ **어떤 변경도 "느낌으로" 좋아졌다고 말할 수밖에 없음**. 개선 자체보다 평가 인프라가 더 시급.

---

## 2. 개선안 카테고리별 정리

### 카테고리 1: 보도자료/참고기사 균형 (사용자가 직접 느낀 문제)

| 번호 | 개선안 | 변경 위치 | 효과 |
|---|---|---|---|
| 1-1 | `LLM_GENERATE_REF_MAX_CHARS` 1200 → 2500 | env | 참고기사 본문이 더 많이 들어감 |
| 1-2 | `LLM_EXTRACT_REF_MAX_CHARS` 700 → 1500 | env | JSON 추출 시점부터 참고기사 정보 보존 |
| 1-3 | `LLM_MAX_RELATED_CHUNKS` 5 → 8 | env | 더 많은 chunk가 컨텍스트에 들어감 |
| 1-4 | 시스템 프롬프트 "background" → "actively incorporate quotes, concrete details" | [llm.py:321](llm.py) | 모델 행동 변화 유도 |
| 1-5 | JSON 추출을 2개로 분리: `main_facts` + `context_facts` | [llm.py:235](llm.py) | 참고기사 사실이 별도 필드로 보존 |
| 1-6 | citation 마커 분포 후처리 검증 (regex로 [1] vs [2]+ 비율 측정) | 신규 함수 | 균형 깨졌을 때 경고/재생성 |
| 1-7 | 참고기사 본문에서 직접 인용문(따옴표) 추출해서 프롬프트에 강제 명시 | [llm.py:746](llm.py) | "꼭 쓸 인용문" 명시로 누락 방지 |

### 카테고리 2: 검색 품질 (재색인 불필요, 즉시 비교 가능)

| 번호 | 개선안 | 변경 위치 | 효과 |
|---|---|---|---|
| 2-1 | RRF `dense_weight` 0.5/0.5 → 0.6/0.4 또는 0.4/0.6 비교 | [config.py:80](config.py) | 도메인에 맞는 균형 |
| 2-2 | 시간 감쇠 반감기 365 → 180 (속보 도메인) | [config.py:86](config.py) | 최신 문서 우선도 ↑ |
| 2-3 | `initial_candidates` 30 → 50, `after_time_decay` 15 → 20 | [config.py:83-84](config.py) | rerank 단계 후보군 확대 |
| 2-4 | `final_results` 10 → 15 비교 | [config.py:85](config.py) | 기자 선택 폭 ↑ |
| 2-5 | document_kind 분리 검색 옵션 추가 (press_release / reference_article / both) | [search.py:28](search.py) | 기자 의도 반영 |
| 2-6 | rerank 모델 비교: `bongsoo/klue-cross-encoder-v1` vs `BAAI/bge-reranker-v2-m3` vs `dragonkue/bge-reranker-v2-m3-ko` | [search.py:148](search.py) | 한국어 reranker 정확도 |
| 2-7 | rerank on/off 토글하여 비용 대비 효과 측정 | env `RERANK_ENABLED` | |
| **2-8** | **⚠️ tsvector 매치 수 측정 (sanity check)** — 보도자료 5건으로 SQL 직접 실행해 평균 매치 수 확인. 0~5건이면 keyword leg 죽은 상태 확정 | dev DB에서 SQL | 진단 |
| **2-9** | **keyword leg ON/OFF 비교 retrieval 평가** — 만약 OFF가 같거나 더 좋으면 keyword leg 통째 제거하고 dense-only로 단순화 | [search.py:181](search.py) 일시 주석 | 빠른 의사결정 |
| **2-10** | **`plainto_tsquery` → `websearch_to_tsquery` 교체** — AND-only를 일부 OR 지원으로 완화 | [search.py:61](search.py) | 매치율 ↑, 코드 변경 1줄 |
| **2-11** | **쿼리 핵심 키워드 추출 후 OR 조합** — 한글 2글자+ 명사만 정규식으로 뽑아 `to_tsquery`에 `\|`로 OR 결합. 조사 휴리스틱 제거 포함 | [search.py:52](search.py) 재작성 | 정밀도 ↓, 매치율 ↑↑ |

### 카테고리 3: 검색 인덱스 보강 (한 번 재구축 필요)

| 번호 | 개선안 | 변경 위치 | 효과 |
|---|---|---|---|
| 3-1 | BGE-M3 sparse vector 활성화 + sparse_weight 추가 | [embedder.py:94](embedder.py), schema에 컬럼 추가 | 키워드 검색 보강, 비용 0 |
| 3-2 | tsvector를 한국어 형태소(kiwi)로 변경 — ingest 시 명사만 추출해 `keyword_text` 별도 컬럼에 저장 후 GIN 인덱스 | [ingest.py:202](ingest.py), [search.py:58](search.py), schema | 한국어 매치율 ↑↑ |
| **3-4** | **keyword leg 통째 대체: tsvector 제거 + BGE-M3 sparse + dense 하이브리드** — 카테고리 2의 진단 결과 tsvector가 죽었다면 가장 깔끔한 해결책 | schema/search/embedder 전반 | 한국어 토큰화 모델이 자동 처리 |
| 3-3 | meta_prefix에서 date만 부분 포함 (source는 여전히 제외) | [embedder.py:31](embedder.py) | 시간 컨텍스트 회복 |

**카테고리 2 & 3 의사결정 분기** (tsvector 진단 결과에 따라):

```
2-8 SQL 매치 수 측정
    │
    ├─ 평균 매치 0~5건 → keyword leg 죽음 확정
    │       │
    │       ├─ 빠른 응급조치: 2-10 (websearch_to_tsquery) 또는 2-11 (키워드 추출)
    │       └─ 근본 해결: 3-4 (BGE-M3 sparse로 교체) 또는 3-2 (kiwi 형태소)
    │
    └─ 평균 매치 20+ 건 → keyword leg 정상 작동
            │
            └─ 2-1 (RRF 가중치 튜닝)부터 진행

### 카테고리 4: 청킹·전처리 (재색인 필요, 시간 비용 큼)

| 번호 | 개선안 | 변경 위치 | 효과 |
|---|---|---|---|
| 4-1 | chunk_size 400 → 600/800 비교 | [chunker.py:17](chunker.py) | 사실 단위 보존 |
| 4-2 | separators에 한국어 종결어미 추가 `["다. ", "요. ", "다.\n", ...]` | [chunker.py:12](chunker.py) | 자연스러운 경계 |
| 4-3 | body_text와 pdf_text를 다른 chunk_size로 처리 | [ingest.py:202](ingest.py) | 도메인별 최적화 |
| 4-4 | LangChain `SemanticChunker` 비교 (의미 기반 분할) | 신규 | 토픽 단위 chunk |
| 4-5 | 중복 임계값 0.95 → 0.97 | [ingest.py:275](ingest.py) | 정보 손실 감소 |

### 카테고리 5: Contextual Retriever 최적화

| 번호 | 개선안 | 변경 위치 | 효과 |
|---|---|---|---|
| 5-1 | 같은 doc의 모든 chunk를 1콜로 batch 처리 | [contextualizer.py](contextualizer.py) 재설계 | LLM 호출 수 5-10배 ↓ |
| 5-2 | 모델 선택 가능하게 (Haiku 4.5, Nova-lite) | [contextualizer.py:90](contextualizer.py) | 비용 ↓, provider 통일 |
| 5-3 | doc 전체 1회 요약 + chunk별 위치 정보만 부여 (LLM 호출 doc당 1회로 축소) | 재설계 | 토큰 비용 최소화 |
| 5-4 | contextual prefix ON/OFF의 retrieval 영향 정량 비교 | 평가 스크립트 | 사용 여부 자체 검증 |

### 카테고리 6: UI/UX

| 번호 | 개선안 | 위치 | 효과 |
|---|---|---|---|
| 6-1 | 참고기사 카드에 chunk의 `original_text` (400자) 풀로 노출 | frontend | 기자가 어느 부분인지 명확히 인지 |
| 6-2 | 같은 raw_document에서 여러 chunk 잡힐 때 그룹핑 | frontend | 중복 인식 부담 ↓ |
| 6-3 | rerank_score 표시 (왜 추천됐는지) | frontend | 기자 의사결정 보조 |
| 6-4 | 검색 모드 토글: 참고기사만 / 보도자료만 / 전체 | frontend + [search.py](search.py) | 기자 의도 직접 반영 |
| 6-5 | 생성된 기사 본문의 [1][2] 마커 호버 시 출처 chunk 미리보기 | frontend | 사실 검증 UX |

### 카테고리 7: 평가 인프라 (다른 모든 개선의 전제)

| 번호 | 개선안 | 위치 | 효과 |
|---|---|---|---|
| 7-1 | `eval/eval_selfretrieval.py` — 보도자료 자체 쿼리로 자기 chunk가 top-k에 잡히는지 측정 | 신규 | 라벨링 없이 빠른 sanity check |
| 7-2 | 골든셋 라벨링 (보도자료 20-30건 × 관련 chunk 3-5개) | `eval/goldenset.json` | recall@k, MRR 정확 측정 |
| 7-3 | LLM-as-judge 평가 (Claude가 retrieval 결과 채점) | 신규 | 사람 라벨링 부담 ↓ |
| 7-4 | citation 분포 검증 스크립트 (생성 기사가 출처를 골고루 인용했나) | 신규 | 카테고리 1 검증용 |
| 7-5 | 실험 기록 양식 (`eval/results.csv`) | 신규 | 변경 이력 + metric 추적 |
| 7-6 | dev DB 셋업 (EC2에 `rag_db_dev` + SSH 터널) | 인프라 | 운영 무영향 실험 환경 |

---

## 3. 우선순위 매트릭스 (영향도 × 난이도)

```
영향도 ↑
       │ [2-8] tsvector 진단     [1-5] JSON 분리       [3-1] sparse
       │ [1-1~3] env             [4-1] 청크크기        [3-2] 형태소
       │ [7-6] dev DB            [5-1] context batch  [3-4] sparse 교체
       │ [7-1] eval script       [2-9] keyword OFF
       │                         [1-4] 프롬프트        [2-5] kind 필터
       │ [2-1] RRF               [2-6] rerank 모델
       │ [2-2] 시간감쇠          [2-10/11] tsquery
       │ [4-5] 중복 임계
       │ [1-6] citation 검증
       │ [6-1] chunk 노출
       │
       │ [5-2] context 모델      [6-2~5] UI           [4-4] semantic chunk
       │ [4-2] separators        [7-2] 골든셋          [5-3] doc 요약
       │ [7-4] 분포 스크립트     [7-3] LLM-as-judge
       │                                                                      
       └───────────────────────────────────────────────────────────→ 난이도
        쉬움                    중간                    어려움
```

**가성비 최고 5개** (영향 ↑ × 난이도 ↓): `2-8` (tsvector 진단 SQL), `1-1~3` (env), `7-6` (dev DB), `7-1` (eval script), `2-1` (RRF)

⚠️ **2-8을 가장 먼저 해야 하는 이유**: tsvector가 죽어있다면 카테고리 2의 다른 검색 튜닝(RRF 가중치 등)이 의미 없을 수 있음. dense-only 상태에서 가중치 조정해봤자 한쪽은 빈 결과. 진단 먼저 → 그에 따라 keyword leg를 살릴지/제거할지/교체할지 결정.

---

## 4. 단계별 실행 계획

### Phase 1: 평가·실험 인프라 구축 (1-2일)
> 모든 변경의 전제. 측정 없이는 개선이 아니라 변경.

1. EC2 postgres에 `rag_db_dev` 생성 + 운영 데이터 복제
2. SSH 터널 + 로컬 `.env.dev` 셋업
3. `eval/eval_selfretrieval.py` 작성 — recall@10, MRR
4. baseline 측정 → `eval/results.csv` 기록
5. (선택) 골든셋 20건 라벨링

**완료 조건**: 같은 파라미터로 2번 측정 시 동일한 metric 나옴 → 측정 환경 안정

### Phase 1.5: tsvector 키워드 검색 진단 (반나절) ⚠️ 시급
> Phase 2 검색 튜닝 전에 반드시 선행. 죽은 코드 위에서 가중치 조정해봐야 의미 없음.

1. **2-8 진단 SQL** dev DB에서 보도자료 5건으로 실행:
   ```sql
   SELECT count(*)
   FROM documents d
   WHERE to_tsvector('simple', d.full_text)
      @@ plainto_tsquery('simple', '<보도자료 본문 일부>');
   ```
2. **2-9 keyword leg ON/OFF** 평가 비교 — `search.py:181`에서 `kw_results = []`로 강제한 뒤 retrieval 측정
3. 결과에 따라 분기:

   | 진단 결과 | 다음 행동 |
   |---|---|
   | 평균 매치 0~5건 & OFF가 같거나 좋음 | keyword leg 통째 제거 (dense-only) 또는 3-4 (sparse 교체) 진행 |
   | 평균 매치 0~5건 & OFF가 나쁨 | 응급: 2-10 (websearch_to_tsquery) 또는 2-11 (키워드 추출 OR) 적용 |
   | 평균 매치 20+ & 효과 있음 | 정상 작동 — Phase 2로 진행 |

**완료 조건**: keyword leg의 실제 기여도가 숫자로 명시됨.

### Phase 2: env 조정으로 즉시 효과 검증 (반나절)
> 코드 변경 0, 재색인 0.

| 실험 | 파라미터 |
|---|---|
| Baseline | 현재 그대로 |
| Exp-A | `LLM_GENERATE_REF_MAX_CHARS=2500`, `LLM_EXTRACT_REF_MAX_CHARS=1500`, `LLM_MAX_RELATED_CHUNKS=8` |
| Exp-B | Exp-A + RRF dense 0.4 / keyword 0.6 (단, Phase 1.5에서 keyword leg가 작동 확인된 경우만) |
| Exp-C | Exp-B + 시간 감쇠 반감기 180 |

**측정**: 정량(recall@10, MRR) + 정성(같은 보도자료로 기사 생성 후 참고기사 인용 분포 육안 확인).

### Phase 3: 프롬프트·후처리 (1일)
> 코드 변경 있지만 색인 영향 없음.

- 1-4: 시스템 프롬프트 톤 조정 (3가지 버전 A/B)
- 1-6: citation 분포 검증 후처리 추가
- 2-5: document_kind 분리 검색 옵션 (API 파라미터 노출)

### Phase 4: 인덱스 보강 (2-3일, 재색인 필요)
> 한 번에 묶어서 진행. dev DB에서.

- 3-1: BGE-M3 sparse 활성화 (schema에 `embedding_sparse` 컬럼 추가, hybrid search에 sparse leg 추가)
- 3-2: tsvector → kiwi 형태소 (또는 sparse로 대체)
- 4-1: 청크 600/150 비교
- 4-2: 한국어 separators 추가
- 4-5: 중복 임계값 0.97

각 변경마다 재색인 + 평가. 영향도 큰 것부터 1개씩.

### Phase 5: Contextual Retriever 재설계 (2-3일)
> 비용·속도 동시 개선.

- 5-1, 5-2: doc 단위 batch + Haiku로 변경
- 5-4: ON/OFF retrieval 영향 비교 → 만약 영향이 미미하면 OFF로 운영 가능

### Phase 6: UI 개선 (별도 트랙)
> 백엔드 변경과 병렬 진행 가능.

- 6-1, 6-2: chunk 본문 노출 + 그룹핑
- 6-3: rerank_score 표시
- 6-4: 검색 모드 토글
- 6-5: citation 호버 미리보기

### Phase 7: 운영 배포
> 최적 조합 확정 후.

1. EC2 main DB에 동일한 schema/index 변경 적용
2. 운영 데이터 재색인 (필요 시 점진적)
3. 변경된 env 운영에 반영
4. 모니터링: 일간 검색 latency, 생성 기사 citation 분포

---

## 5. 검증 시나리오 (정성 평가용 체크리스트)

같은 보도자료로 변경 전후 기사를 생성해 다음 항목 비교:

- [ ] 참고기사의 **고유 표현/단어**가 새 기사에 등장하는가?
- [ ] 참고기사에 있는 **숫자, 인용문**이 인용 마커와 함께 들어갔는가?
- [ ] citation 마커가 `[1]`(보도자료)만 있지 않고 다양한가?
- [ ] 보도자료에 없는 **배경/맥락**이 참고기사로부터 추가됐는가?
- [ ] 기사 길이 1400-2200자 범위 안에 있는가?
- [ ] 사실 오류(환각) 없이 출처와 일치하는가?

---

## 6. 환경변수 Quick Reference

실험 시 자주 토글할 변수들. `.env.dev`에 모아두면 비교 쉬움.

```bash
# 카테고리 1: 보도자료/참고기사 균형
LLM_EXTRACT_MAIN_MAX_CHARS=1800     # 1800 → 2400 (보도자료 더 보존)
LLM_EXTRACT_REF_MAX_CHARS=700       # 700 → 1500 (참고기사 더 보존)
LLM_GENERATE_MAIN_MAX_CHARS=4200    # 그대로 또는 ↑
LLM_GENERATE_REF_MAX_CHARS=1200     # 1200 → 2500 (가장 중요)
LLM_MAX_RELATED_CHUNKS=5            # 5 → 8

# 카테고리 2: 검색 파라미터 (config.py에 이미 있지만 env로 노출 권장)
# SearchConfig를 환경변수로 받게 리팩터링 필요

# 카테고리 5: Contextualizer
INGEST_USE_CONTEXT=0|1
# LLM_CONTEXT_MODEL_KEY=claude-haiku-4-5  (신규 필요)
# LLM_CONTEXT_BATCH_MODE=per_doc          (신규 필요)

# 평가 모드
PG_DATABASE=rag_db_dev                # 운영 DB 보호
```

---

## 7. 다음 액션

가장 먼저 해야 할 일은 **Phase 1 평가 인프라**입니다. 측정 도구 없이 환경변수만 바꾸면 "좀 나아진 것 같은데?" 수준의 판단밖에 못 합니다.

추천 순서:
1. dev DB 셋업 (반나절)
2. self-retrieval 평가 스크립트 (2-3시간)
3. baseline 기록
4. **Phase 1.5 tsvector 진단** (반나절) — 가장 먼저 해야 할 핵심 진단
5. 진단 결과 따라 Phase 2 또는 Phase 3-4 우선순위 결정
6. 결과 보며 카테고리 1 env 실험 진행

이후는 결과 보며 우선순위 재조정.
