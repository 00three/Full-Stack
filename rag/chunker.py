"""
청킹 모듈 (가이드 3단계)

문장 단위 청킹: 한국어 종결어미 기준으로 문장을 분리한 뒤,
target_size 근처에서 문장 경계에 맞춰 끊음.
문장 중간에서 절대 자르지 않음.
"""

import re
import os


# ──────────────────────────────────────────────
# 한국어 문장 분리
# ──────────────────────────────────────────────

# 한국어 종결어미 + 문장부호 패턴
# 다. 요. 죠. 음. 됨. 함. 니다. 습니다. 했다. 됐다. 한다. 이다. 였다. 인다. 왔다. 갔다. ...
_SENT_END = re.compile(
    r'(?<=[다요죠음임됨함까])[.!?]\s+'     # 종결어미 + 문장부호 + 공백
    r'|(?<=[다요죠음임됨함까])[.!?](?=\n)'  # 종결어미 + 문장부호 + 줄바꿈
    r'|(?<=[.!?])\s*\n\s*'                  # 문장부호 + 줄바꿈 (문단 경계)
)


def split_sentences(text: str) -> list[str]:
    """한국어 텍스트를 문장 단위로 분리."""
    if not text or not text.strip():
        return []

    parts = _SENT_END.split(text)
    sentences = []
    for p in parts:
        stripped = p.strip()
        if stripped:
            sentences.append(stripped)
    return sentences


# ──────────────────────────────────────────────
# 문장 기반 청킹
# ──────────────────────────────────────────────

def split(
    text: str,
    target_size: int = int(os.getenv("CHUNK_TARGET_SIZE", "600")),
    max_size: int = int(os.getenv("CHUNK_MAX_SIZE", "1200")),
    overlap_sentences: int = int(os.getenv("CHUNK_OVERLAP_SENTENCES", "1")),
) -> list[str]:
    """
    문장 단위로 그룹핑하여 chunk 생성.

    - target_size: 이 글자수에 도달하면 현재 chunk를 끊고 새 chunk 시작 (soft limit)
    - max_size: 단일 문장이 이보다 길면 예외적으로 강제 분할 (hard limit)
    - overlap_sentences: 인접 chunk에 겹치는 문장 수

    기존 split() 함수와 동일한 시그니처 유지 (호출부 변경 불필요).
    """
    if not text or not text.strip():
        return []

    # 1) 먼저 문단 단위로 큰 분리
    paragraphs = re.split(r'\n{2,}', text.strip())

    # 2) 각 문단을 문장으로 분리
    all_sentences = []
    for para in paragraphs:
        sents = split_sentences(para)
        if sents:
            all_sentences.extend(sents)
        elif para.strip():
            all_sentences.append(para.strip())

    if not all_sentences:
        return [text.strip()] if text.strip() else []

    # 3) 문장들을 target_size 기준으로 그룹핑
    chunks = []
    current: list[str] = []
    current_len = 0

    for sent in all_sentences:
        sent_len = len(sent)

        # 현재 chunk + 새 문장이 target 초과 → 현재 chunk 확정
        if current and current_len + sent_len > target_size:
            chunks.append('\n'.join(current))
            # overlap: 마지막 N개 문장 유지
            if overlap_sentences > 0:
                current = current[-overlap_sentences:]
                current_len = sum(len(s) for s in current)
            else:
                current = []
                current_len = 0

        # 매우 긴 문장 → 강제 분할 (예외 케이스)
        if sent_len > max_size:
            if current:
                chunks.append('\n'.join(current))
                current = []
                current_len = 0
            for i in range(0, sent_len, max_size):
                chunks.append(sent[i:i + max_size])
            continue

        current.append(sent)
        current_len += sent_len

    if current:
        chunks.append('\n'.join(current))

    return chunks
