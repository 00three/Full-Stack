"""추상화 레이어 - 크롤러, RAG, LLM 미정. 담당 확정 시 구현체 교체."""

from backend.adapters.providers import PressReleaseProvider
from backend.adapters.mock_provider import MockPressReleaseProvider
from backend.adapters.rag import RAGService
from backend.adapters.generator import ArticleGenerator

__all__ = [
    "PressReleaseProvider",
    "MockPressReleaseProvider",
    "RAGService",
    "ArticleGenerator",
]
