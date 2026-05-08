"""
청킹 모듈 (가이드 3단계)

LangChain RecursiveCharacterTextSplitter로 의미 단위 보존하며 분할.
- chunk_size=400, overlap=100 (가이드 기본값, 실험으로 조정 예정)
- 우선순위: 문단(\\n\\n) → 줄바꿈(\\n) → 마침표(. ) → 공백
"""

from langchain_text_splitters import RecursiveCharacterTextSplitter


_DEFAULT_SEPARATORS = ["\n\n", "\n", ". ", " "]


def split(
    text: str,
    chunk_size: int = 400,
    chunk_overlap: int = 100,
) -> list[str]:
    """
    텍스트를 chunk_size 자 이내로 분할. 짧은 텍스트는 단일 chunk.
    빈 문자열 입력 → 빈 리스트.
    """
    if not text or not text.strip():
        return []

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=_DEFAULT_SEPARATORS,
        length_function=len,
        is_separator_regex=False,
    )
    return splitter.split_text(text)
