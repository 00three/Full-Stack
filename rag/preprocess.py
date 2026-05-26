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

# UI/광고/구독 잡음 패턴 (줄 단위 제거)
_NOISE_LINES = re.compile(
    r"^("
    r"글씨\s*크게보기|글자\s*크기\s*조절|본문\s*듣기|원고료.*응원.*|"
    r"추천\s*\d*|댓글|공유|인쇄|스크랩|"
    r"가\s+가\s+가|"
    r"로그인.*(?:이용|보실|내용).*|"
    r"지면보기.*이용 가능합니다|"
    r"더중앙플러스.*|"
    r"최근 \d+개월.*열람.*|"
    r"로그인 하시겠습니까|"
    r"무단\s*전재.*금지|"
    r"저작권.*(?:뉴스|신문|일보|미디어)|"
    r"Copyright.*|"
    r"ⓒ.*|"
    r"▶.*구독.*|"
    r"※\s*(?:구독|채널|알림).*|"
    r"기사제보.*|"
    r"\[.*기자\]$|"
    r"\s*ㅣ\s*$|"
    r"\s*최종\s*업데이트.*|"
    r"관련기사|더보기|"
    r".*기사\s*잘\s*읽으셨.*|"
    r"후원은\s*더\s*좋은.*|"
    r"\d+천원|\d+만원|정기후원|후원하기|"
    r"#[가-힣A-Za-z]+|"
    r"구독중?|이전|다음|"
    r"좋아요|슬퍼요|화나요|후속요청|북마크|"
    r"카카오톡|페이스북|네이버\s*밴드|URL\s*복사|"
    r"폰트\s*\d+단계.*|글자크기|본문\s*글자.*|"
    r"프린트|제보|닫기|등록|"
    r"URL이\s*복사되었습니다|"
    r"뉴스\s*홈|뉴스\s*모아보기|뉴스데스크|뉴스투데이|날짜별|분야별|지역별|전국뉴스|뉴스제보|"
    r"데스크인터뷰.*|"
    r"share|print|"
    r"\d+/\s*$|"
    r".*@.*\.co\.kr.*|.*@.*\.com.*"
    r")$",
    re.MULTILINE
)


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

    # UI/광고 잡음 줄 제거
    text = _NOISE_LINES.sub("", text)

    # 블록 단위 잡음 제거 (관련기사 목록, 해시태그 블록, 기사 하단 잡음)
    text = re.sub(r'관련기사\n(?:.*\n){0,10}더보기', '', text)
    text = re.sub(r'#\s*해시태그\s*\n?', '', text)
    text = re.sub(r'저작권자\s*©.*', '', text)
    text = re.sub(r'[가-힣]{2,4}\s*기자\n', '', text)

    # 공백·개행 정규화
    text = _MULTI_WS.sub(" ", text)
    text = _MULTI_NEWLINE.sub("\n\n", text)

    return text.strip()
