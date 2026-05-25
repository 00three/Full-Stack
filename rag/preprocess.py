"""
전처리 모듈 (가이드 1·2단계)

- 1단계: 크롤러 JSONL 1건 → body_text 추출
- 2단계: HTML 제거 + 공백 정규화 (숫자/단위/영문/구두점은 보존)
- source 정규화: 크롤러 출력값 → ERD 표준 약어
"""

import re

from bs4 import BeautifulSoup


# ──────────────────────────────────────────────
# source 정규화
# ──────────────────────────────────────────────

# 크롤러 출력 → ERD 표준 (KCC | NSP | MBC | NODONG)
SOURCE_MAP = {
    "KCC": "KCC",
    "Broadcast": "MBC",
    "National Assembly": "NSP",
    "Media Union": "NODONG",
}


def normalize_source(source: str) -> str:
    """크롤러 source 값을 ERD 표준 약어로 변환"""
    return SOURCE_MAP.get(source, source)


# ──────────────────────────────────────────────
# 1단계: 텍스트 결합용 분리
# ──────────────────────────────────────────────

def split_inputs(raw: dict) -> dict[str, str]:
    """
    크롤러 JSONL 1건을 data_type별 텍스트 dict로 분리.

    반환: {"body_text": "..."}
    빈 값은 키에서 제외 (청킹 단계에서 skip).
    """
    out = {}
    body = (raw.get("content_text") or "").strip()
    if body:
        out["body_text"] = body

    return out


# ──────────────────────────────────────────────
# 2단계: 텍스트 정제
# ──────────────────────────────────────────────

# 제어문자 제거용 (개행/탭은 살림)
_CTRL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# 공백 정규화: 공백 문자가 2개 이상 연속이면 1개로
_MULTI_WS = re.compile(r"[ \t  -​]+")

# 줄바꿈 정규화: 3개 이상 연속이면 2개(문단 구분)로
_MULTI_NEWLINE = re.compile(r"\n{3,}")


def clean_text(text: str) -> str:
    """
    HTML 제거 + 공백 정규화. 의미 토큰은 모두 보존.

    보존되는 것: 숫자, %, ., ,, -, 영문, 한글, 한자, 일반 구두점
    제거되는 것: HTML 태그, 제어문자, 과도한 공백/개행
    """
    if not text:
        return ""

    # HTML 제거 (크롤러가 1차로 했지만 PDF/HWP 추출본엔 잔여 가능)
    if "<" in text and ">" in text:
        text = BeautifulSoup(text, "lxml").get_text(separator=" ")

    # 제어문자 제거
    text = _CTRL_CHARS.sub("", text)

    # 공백·개행 정규화
    text = _MULTI_WS.sub(" ", text)
    text = _MULTI_NEWLINE.sub("\n\n", text)

    return text.strip()
