"""
임베딩 모듈 (가이드 5·6·7단계)

- 5단계: 메타데이터 prefix 조립
- 6단계: full_text = context_prefix + meta_prefix + original_text
- 7단계: BGE-M3로 1024차원 dense vector 생성

BGEEmbedder는 싱글톤 + lazy load. 첫 호출 시 모델 ~2GB 다운로드 (HuggingFace).
"""

from __future__ import annotations

import os

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

    meta_prefix(source|date|title 헤더)는 임베딩에서 의도적으로 제외한다.
    BGE-M3가 source 토큰(KCC/NSP/MBC/NODONG)을 강하게 학습하면서
    같은 출처 청크끼리 cosine 유사도가 압도적으로 높아져 cross-source
    검색이 막히는 부작용이 있었음. source·date·title은 별도 컬럼에
    그대로 저장되므로 메타 필터링·표시에는 영향 없음.
    """
    parts = [p for p in (context_prefix, original_text) if p]
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

        torch_threads = int(os.getenv("PYTORCH_NUM_THREADS", os.getenv("TORCH_NUM_THREADS", "4")))
        if torch_threads > 0:
            torch.set_num_threads(torch_threads)
            try:
                torch.set_num_interop_threads(max(1, min(2, torch_threads)))
            except RuntimeError:
                pass

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
