"""기사 생성 인터페이스. LLM 담당 미정 시 목업 사용."""

from typing import Protocol


class ArticleGenerator(Protocol):
    """기사 생성. 추후 LLM 연동 구현체로 교체."""

    def generate(self, press_release_id: str, context: dict) -> dict:
        """속보기사 생성 (title, lead, body)"""
        ...
