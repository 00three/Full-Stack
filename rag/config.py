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
    # provider: "openai" | "anthropic" (기본 openai로 backward-compat)
    provider: str = os.getenv("LLM_PROVIDER", "openai")

    # OpenAI
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    # Anthropic
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    anthropic_model: str = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")

    # 공통
    max_tokens: int = 2000
    temperature: float = 0.3

    # ─ backward-compat shim (기존 코드가 llm_config.api_key / .model 참조했던 케이스 대비)
    @property
    def api_key(self) -> str:
        return self.anthropic_api_key if self.provider == "anthropic" else self.openai_api_key

    @property
    def model(self) -> str:
        return self.anthropic_model if self.provider == "anthropic" else self.openai_model


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
