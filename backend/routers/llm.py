"""LLM option APIs."""

from fastapi import APIRouter

from backend.llm_catalog import public_model_catalog


router = APIRouter(prefix="/llm", tags=["llm"])


@router.get("/models")
def list_models():
    """Return the server-managed model allowlist for the generation UI."""
    return public_model_catalog()
