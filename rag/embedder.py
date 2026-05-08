"""
임베딩 모듈 (가이드 5·6·7단계)

- 5단계: 메타데이터 prefix 조립
- 6단계: full_text = context_prefix + meta_prefix + original_text
- 7단계: BGE-M3로 1024차원 dense vector 생성

BGEEmbedder는 싱글톤 + lazy load. 첫 호출 시 모델 ~2GB 다운로드 (HuggingFace).
"""

from __future__ import annotations

import numpy as np


# ──────────────────────────────────────────────
# 5단계: 메타데이터 prefix
# ──────────────────────────────────────────────

def make_meta_prefix(source: str, date: str, title: str) -> str:
    """예: '[KCC | 2026-03-18 | 소상공인 점포 정보 전송 서비스]'"""
    return f"[{source} | {date} | {title}]"


# ──────────────────────────────────────────────
# 6단계: full_text 조립
# ──────────────────────────────────────────────

def make_full_text(
    context_prefix: str,
    meta_prefix: str,
    original_text: str,
) -> str:
    """
    검색 임베딩·tsvector 대상이 되는 텍스트.
    context_prefix가 빈 문자열이면 (4단계 skip 시) 자동으로 제외됨.
    """
    parts = [p for p in (context_prefix, meta_prefix, original_text) if p]
    return "\n".join(parts)


# ──────────────────────────────────────────────
# 7단계: BGE-M3 임베딩 (싱글톤)
# ──────────────────────────────────────────────

class BGEEmbedder:
    """BGE-M3 dense 임베딩 (1024차원). 프로세스당 1개 인스턴스만 모델 로딩."""

    _instance: BGEEmbedder | None = None

    def __new__(cls) -> BGEEmbedder:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._model = None
        return cls._instance

    def _load(self) -> None:
        if self._model is not None:
            return

        from FlagEmbedding import BGEM3FlagModel
        import torch

        # fp16은 CUDA에서만 안전 (Mac MPS/CPU는 fp32)
        use_fp16 = torch.cuda.is_available()
        self._model = BGEM3FlagModel("BAAI/bge-m3", use_fp16=use_fp16)

    def encode(self, texts: list[str], batch_size: int = 32) -> np.ndarray:
        """배치 임베딩. 반환 shape: (N, 1024), dtype: float32"""
        if not texts:
            return np.zeros((0, 1024), dtype=np.float32)

        self._load()
        out = self._model.encode(
            texts,
            batch_size=batch_size,
            return_dense=True,
            return_sparse=False,
            return_colbert_vecs=False,
        )
        return out["dense_vecs"]

    def encode_one(self, text: str) -> np.ndarray:
        """단일 텍스트 → shape (1024,)"""
        return self.encode([text])[0]


# ──────────────────────────────────────────────
# query 임베딩 유틸 (search.py에서 호출)
# ──────────────────────────────────────────────

def encode_query(text: str) -> list[float]:
    """검색 쿼리 1건을 임베딩하여 pgvector가 받는 list[float]로 반환."""
    return BGEEmbedder().encode_one(text).tolist()
