"""
메인 파이프라인: 검색 → LLM → 기사 출력
"""

from .search import hybrid_search
from .llm import extract_json, generate_article, verify_article


def run(query_text: str, query_embedding: list[float], selected_indices: list[int] | None = None) -> dict:
    """
    RAG 전체 파이프라인 실행

    Args:
        query_text: 보도자료 텍스트 (검색 쿼리)
        query_embedding: 보도자료 임베딩 벡터 (BGE-M3, 1024차원)
        selected_indices: 기자가 선택한 참고 기사 인덱스 (None이면 전체 사용)

    Returns:
        {
            "search_results": [...],      # 검색된 참고 기사 10개
            "selected_chunks": [...],     # 기자가 선택한 chunk
            "extracted_json": {...},      # 1차 LLM: 핵심 팩트 JSON
            "article": {...},            # 2차 LLM: 생성된 기사
            "verification": {...},       # 3차 LLM: 사실검증 결과
        }
    """

    # 1. 검색: dense + keyword → RRF → 시간 가중치 → Re-ranking → 10개
    search_results = hybrid_search(query_text, query_embedding)

    # 2. 기자 선택 (UI에서 체크박스로 선택한 참고 기사)
    if selected_indices is not None:
        selected_chunks = [search_results[i] for i in selected_indices if i < len(search_results)]
    else:
        selected_chunks = search_results

    # 3. 1차 LLM: JSON 구조화 추출
    extracted_json = extract_json(selected_chunks)

    # 4. 2차 LLM: 기사 생성
    article = generate_article(extracted_json, selected_chunks)

    # 5. 3차 LLM: 사실검증
    verification = verify_article(extracted_json, article)

    return {
        "search_results": search_results,
        "selected_chunks": selected_chunks,
        "extracted_json": extracted_json,
        "article": article,
        "verification": verification,
    }
