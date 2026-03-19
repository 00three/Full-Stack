"""RAG 검색 인터페이스. AI 담당 미정 시 목업 사용."""

from typing import Protocol


class RAGService(Protocol):
    """RAG 검색. 추후 AI 팀 구현체로 교체."""

    def search(self, query: str, top_k: int = 5) -> list[dict]:
        """관련 문서 검색"""
        ...
