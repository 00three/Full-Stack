import os
from dataclasses import dataclass

from dotenv import load_dotenv


# 프로젝트 루트의 .env 자동 로드. 시스템 환경변수가 우선 (덮어쓰기 X).
load_dotenv()


@dataclass
class DBConfig:
    host: str = os.getenv("PG_HOST", "localhost")
    port: int = int(os.getenv("PG_PORT", "5432"))
    database: str = os.getenv("PG_DATABASE", "rag_db")
    user: str = os.getenv("PG_USER", "postgres")
    password: str = os.getenv("PG_PASSWORD", "postgres")

    @property
    def dsn(self) -> str:
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"


@dataclass
class LLMConfig:
    # provider: "openai" | "anthropic" | "bedrock" (기본 openai로 backward-compat)
    provider: str = os.getenv("LLM_PROVIDER", "openai")

    # OpenAI
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    # Anthropic
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    anthropic_model: str = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")

    # Amazon Bedrock
    bedrock_region: str = os.getenv(
        "BEDROCK_REGION",
        os.getenv("AWS_REGION", os.getenv("AWS_DEFAULT_REGION", "ap-northeast-2")),
    )
    bedrock_model_id: str = os.getenv("BEDROCK_MODEL_ID", "")

    # 공통
    max_tokens: int = int(os.getenv("LLM_MAX_TOKENS", "8192"))
    extract_max_tokens: int = int(os.getenv("LLM_EXTRACT_MAX_TOKENS", "500"))
    generate_max_tokens: int = int(os.getenv("LLM_GENERATE_MAX_TOKENS", "8192"))
    extract_model_id: str = os.getenv("LLM_EXTRACT_MODEL_ID", os.getenv("BEDROCK_EXTRACT_MODEL_ID", ""))
    fast_extract: bool = os.getenv("LLM_FAST_EXTRACT", "1") != "0"
    extract_main_max_chars: int = int(os.getenv("LLM_EXTRACT_MAIN_MAX_CHARS", "1800"))
    extract_ref_max_chars: int = int(os.getenv("LLM_EXTRACT_REF_MAX_CHARS", "700"))
    generate_main_max_chars: int = int(os.getenv("LLM_GENERATE_MAIN_MAX_CHARS", "4200"))
    generate_ref_max_chars: int = int(os.getenv("LLM_GENERATE_REF_MAX_CHARS", "1200"))
    max_related_chunks: int = int(os.getenv("LLM_MAX_RELATED_CHUNKS", "5"))
    temperature: float = float(os.getenv("LLM_TEMPERATURE", "0.3"))

    # 기사 스타일: "default" (일반 뉴스) | "mediaus" (송창한·고성욱 톤)
    article_style: str = os.getenv("ARTICLE_STYLE", "default")

    # ─ backward-compat shim (기존 코드가 llm_config.api_key / .model 참조했던 케이스 대비)
    @property
    def api_key(self) -> str:
        if self.provider == "anthropic":
            return self.anthropic_api_key
        if self.provider == "bedrock":
            return ""
        return self.openai_api_key

    @property
    def model(self) -> str:
        if self.provider == "anthropic":
            return self.anthropic_model
        if self.provider == "bedrock":
            return self.bedrock_model_id
        return self.openai_model


@dataclass
class SearchConfig:
    dense_weight: float = 0.5       # RRF에서 dense 검색 가중치
    keyword_weight: float = 0.5     # RRF에서 키워드 검색 가중치
    rrf_k: int = 60                 # RRF 상수 (기본값 60)
    initial_candidates: int = 30    # Hybrid 검색 후보 수
    after_time_decay: int = 15      # 시간 가중치 적용 후
    final_results: int = 10         # Re-ranking 후 최종 결과 수
    half_life_days: int = 365       # 시간 감쇠 반감기 (일)


db_config = DBConfig()
llm_config = LLMConfig()
search_config = SearchConfig()
