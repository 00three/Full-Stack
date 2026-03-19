"""목업 보도자료 제공 구현체."""

from backend.adapters.providers import PressReleaseProvider
from backend.data.mock import MOCK_PRESS_RELEASES


class MockPressReleaseProvider:
    """목업 구현. 크롤러 담당 확정 시 실제 구현체로 교체."""

    def get_releases(self) -> list[dict]:
        return MOCK_PRESS_RELEASES
