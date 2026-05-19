"""Server-managed LLM catalog exposed to the frontend."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class LLMModelOption:
    key: str
    label: str
    provider: str
    model_id: str
    family: str


_DEFAULT_MODELS = [
    LLMModelOption(
        "claude-sonnet-4-6",
        "Claude Sonnet 4.6",
        "bedrock",
        "global.anthropic.claude-sonnet-4-6",
        "Claude",
    ),
    LLMModelOption(
        "claude-opus-4-6",
        "Claude Opus 4.6",
        "bedrock",
        "global.anthropic.claude-opus-4-6-v1",
        "Claude",
    ),
    LLMModelOption(
        "claude-opus-4-5",
        "Claude Opus 4.5",
        "bedrock",
        "global.anthropic.claude-opus-4-5-20251101-v1:0",
        "Claude",
    ),
    LLMModelOption(
        "claude-haiku-4-5",
        "Claude Haiku 4.5",
        "bedrock",
        "global.anthropic.claude-haiku-4-5-20251001-v1:0",
        "Claude",
    ),
    LLMModelOption(
        "claude-sonnet-4-5",
        "Claude Sonnet 4.5",
        "bedrock",
        "global.anthropic.claude-sonnet-4-5-20250929-v1:0",
        "Claude",
    ),
    LLMModelOption("nova-2-lite", "Nova 2 Lite", "bedrock", "global.amazon.nova-2-lite-v1:0", "Nova"),
    LLMModelOption("nova-pro", "Nova Pro", "bedrock", "apac.amazon.nova-pro-v1:0", "Nova"),
    LLMModelOption("nova-lite", "Nova Lite", "bedrock", "apac.amazon.nova-lite-v1:0", "Nova"),
    LLMModelOption("nova-micro", "Nova Micro", "bedrock", "apac.amazon.nova-micro-v1:0", "Nova"),
]


def _load_models() -> list[LLMModelOption]:
    raw = os.getenv("BEDROCK_MODEL_CATALOG_JSON", "").strip()
    if not raw:
        return _DEFAULT_MODELS

    try:
        items = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("BEDROCK_MODEL_CATALOG_JSON 파싱에 실패했습니다.") from exc

    if not isinstance(items, list):
        raise RuntimeError("BEDROCK_MODEL_CATALOG_JSON은 배열이어야 합니다.")

    models: list[LLMModelOption] = []
    seen_keys: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            raise RuntimeError("BEDROCK_MODEL_CATALOG_JSON 항목은 객체여야 합니다.")
        try:
            model = LLMModelOption(
                key=str(item["key"]),
                label=str(item["label"]),
                provider=str(item.get("provider") or "bedrock"),
                model_id=str(item["model_id"]),
                family=str(item.get("family") or "Custom"),
            )
        except KeyError as exc:
            raise RuntimeError(f"BEDROCK_MODEL_CATALOG_JSON 필수 필드 누락: {exc.args[0]}") from exc
        if model.key in seen_keys:
            raise RuntimeError(f"BEDROCK_MODEL_CATALOG_JSON 중복 key: {model.key}")
        seen_keys.add(model.key)
        models.append(model)

    if not models:
        raise RuntimeError("BEDROCK_MODEL_CATALOG_JSON에 모델이 없습니다.")
    return models


def get_model_catalog() -> list[LLMModelOption]:
    return _load_models()


def get_default_model_key() -> str:
    configured = os.getenv("BEDROCK_DEFAULT_MODEL_KEY", "claude-sonnet-4-6")
    catalog = get_model_catalog()
    if any(model.key == configured for model in catalog):
        return configured
    return catalog[0].key


def resolve_model(model_key: str | None) -> LLMModelOption:
    effective_key = model_key or get_default_model_key()
    for model in get_model_catalog():
        if model.key == effective_key:
            return model
    raise ValueError(f"허용되지 않은 모델입니다: {effective_key}")


def public_model_catalog() -> dict:
    return {
        "default_model_key": get_default_model_key(),
        "models": [
            {
                key: value
                for key, value in asdict(model).items()
                if key != "model_id"
            }
            for model in get_model_catalog()
        ],
    }
