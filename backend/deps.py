"""FastAPI 의존성. 추상화 구현체 주입.

USE_MOCK 환경변수로 Mock/실제 구현 토글:
  USE_MOCK=1  → 기존 mock 사용 (DB·LLM 없이 백엔드 단독 실행)
  USE_MOCK=0  → 실제 RAG/DB 연결 (default)
"""

import os

_USE_MOCK = os.getenv("USE_MOCK", "0") == "1"


# ──────────────────────────────────────────────
# PressReleaseProvider
# ──────────────────────────────────────────────

if _USE_MOCK:
    from backend.adapters.mock_provider import MockPressReleaseProvider
    _provider = MockPressReleaseProvider()
else:
    from backend.adapters.db_provider import DBPressReleaseProvider
    _provider = DBPressReleaseProvider()


def get_press_release_provider():
    """보도자료 제공자."""
    return _provider


# ──────────────────────────────────────────────
# RAGService
# ──────────────────────────────────────────────

_rag_service = None


def get_rag_service():
    """관련 chunk 검색 (rag.search.hybrid_search 래퍼)."""
    global _rag_service
    if _rag_service is None:
        if _USE_MOCK:
            from backend.adapters.mock_provider import MockRAGService
            _rag_service = MockRAGService()
        else:
            from backend.adapters.rag_service import DBRAGService
            _rag_service = DBRAGService()
    return _rag_service


# ──────────────────────────────────────────────
# ArticleGenerator
# ──────────────────────────────────────────────

_article_generator = None


def get_article_generator():
    """기사 생성기 (rag.llm 3단계 체인)."""
    global _article_generator
    if _article_generator is None:
        if _USE_MOCK:
            from backend.adapters.mock_provider import MockArticleGenerator
            _article_generator = MockArticleGenerator()
        else:
            from backend.adapters.article_generator import LLMArticleGenerator
            _article_generator = LLMArticleGenerator()
    return _article_generator
