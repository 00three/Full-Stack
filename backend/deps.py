"""FastAPI 의존성. 추상화 구현체 주입."""

from backend.adapters.mock_provider import MockPressReleaseProvider

_provider = MockPressReleaseProvider()


def get_press_release_provider():
    """보도자료 제공자. 담당 확정 시 실제 구현체 반환하도록 수정."""
    return _provider
