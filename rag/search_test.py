"""검색 동작 검증 (end-to-end test). 단발성 스크립트."""

from rag.embedder import encode_query
from rag.search import hybrid_search


def main() -> None:
    query = "방송 토론 지방선거"
    print(f"query: {query}")

    emb = encode_query(query)
    print(f"embedding dim: {len(emb)}")

    results = hybrid_search(query, emb)
    print(f"\n검색 결과 {len(results)}개:")
    for i, r in enumerate(results):
        print(f"  [{i+1}] {r['chunk_id']}  rerank={r['rerank_score']:.3f}  "
              f"rrf={r.get('rrf_score', 0):.3f}")
        print(f"      {r['original_text'][:100]}")


if __name__ == "__main__":
    main()
