"""보도자료 제공 인터페이스. 크롤러 담당 미정 시 목업 사용."""

from typing import Protocol


class PressReleaseProvider(Protocol):
    """보도자료 목록 제공. 추후 크롤러 구현체로 교체."""

    def get_releases(self) -> list[dict]:
        """보도자료 목록 반환 (id, title, source, date, detail_url)"""
        ...
