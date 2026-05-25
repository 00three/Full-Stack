"""기사 생성 실제 구현체. rag.llm 3단계 체인."""

from __future__ import annotations

from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor, TimeoutError
import queue
import re
import threading
import time

from rag.config import llm_config
from rag.llm import (
    extract_json,
    generate_article,
    parse_article_text,
    stream_generate_article_text,
    verify_article,
)


_PROGRESS_INTERVAL_SECONDS = 2.5
_MEDIAUS_BYLINE_RE = re.compile(r"^\s*\[[^\]=\n]+=[^\]\n]+ 기자\]\s*")


class LLMArticleGenerator:
    """선택된 보도자료 + 참고기사 chunk로 LLM 3단계 호출하여 기사 생성."""

    def generate(
        self,
        press_releases: list[dict],
        related_chunks: list[dict],
        *,
        provider: str | None = None,
        model: str | None = None,
        style: str | None = None,
        tone: str | None = None,
        created_by: str | None = None,
    ) -> dict:
        """
        Args:
            press_releases: [{id, title, source, date, content_text, detail_url}, ...]
            related_chunks: [{chunk_id, source, date, title, original_text, full_text}, ...]
        Returns:
            {title, lead, body, citations, extracted_json}
        """
        merged = self._build_merged_chunks(press_releases, related_chunks)
        citations = self._build_citations(press_releases, related_chunks)
        extract_model = self._extract_model(provider, model)

        # LLM 1차: JSON 추출
        try:
            extracted = (
                self._local_extract_json(merged)
                if llm_config.fast_extract
                else extract_json(merged, provider=provider, model=extract_model)
            )
        except Exception as e:
            extracted = {
                "who": "-", "policy": "-", "decision": "-",
                "target": "-", "numbers": "-", "origin": "-",
                "_error": f"extract_json 실패: {e}",
            }

        # LLM 2차: 기사 생성
        try:
            article = generate_article(
                extracted,
                merged,
                provider=provider,
                model=model,
                style=style,
                tone=tone,
            )
        except Exception as e:
            article = {
                "title": "(기사 생성 실패)",
                "lead": "",
                "body": f"LLM 호출 실패: {e}",
            }
        article = self._apply_style_postprocess(
            article,
            style=style,
            created_by=created_by,
        )

        return {
            "title": article.get("title", ""),
            "lead": article.get("lead", ""),
            "body": article.get("body", ""),
            "genre": article.get("genre", ""),
            "citations": citations,
            "extracted_json": extracted,
        }

    def stream_generate(
        self,
        press_releases: list[dict],
        related_chunks: list[dict],
        *,
        provider: str | None = None,
        model: str | None = None,
        style: str | None = None,
        tone: str | None = None,
        created_by: str | None = None,
    ) -> Iterator[dict]:
        """생성 단계를 event dict로 stream."""
        merged = self._build_merged_chunks(press_releases, related_chunks)
        citations = self._build_citations(press_releases, related_chunks)

        if llm_config.fast_extract:
            yield {
                "type": "stage",
                "stage": "extracting",
                "message": "핵심 사실을 빠르게 정리하는 중입니다.",
            }
            extracted = self._local_extract_json(merged)
        else:
            extract_model = self._extract_model(provider, model)
            yield {
                "type": "stage",
                "stage": "extracting",
                "message": "핵심 사실 추출 요청을 보냈습니다.",
            }
            extracted = yield from self._run_with_progress(
                lambda: extract_json(merged, provider=provider, model=extract_model),
                stage="extracting",
                wait_message="핵심 사실을 추출하는 중입니다.",
            )
        yield {
            "type": "stage",
            "stage": "drafting",
            "message": "핵심 사실 추출 완료. 기사 초안 생성을 요청했습니다.",
            "extracted_json": extracted,
        }

        raw_parts: list[str] = []
        draft_stream = stream_generate_article_text(
            extracted,
            merged,
            provider=provider,
            model=model,
            style=style,
            tone=tone,
        )
        for event in self._stream_tokens_with_progress(draft_stream):
            if event["type"] == "token":
                raw_parts.append(event["delta"])
            yield event

        yield {"type": "stage", "stage": "assembling", "message": "생성문을 정리하는 중입니다."}
        article = parse_article_text("".join(raw_parts))
        article = self._apply_style_postprocess(
            article,
            style=style,
            created_by=created_by,
        )
        article.update({
            "citations": citations,
            "extracted_json": extracted,
        })
        yield {"type": "article", "article": article}

    def extract_only(self, press_release: dict) -> dict:
        """보도자료 1건에서 JSON만 추출 (관련기사 검색 시 동시 표시용)."""
        chunk = {
            "source": press_release.get("source", ""),
            "date": press_release.get("date", ""),
            "title": press_release.get("title", ""),
            "original_text": press_release.get("content_text")
                              or press_release.get("title", ""),
        }
        try:
            return extract_json([chunk])
        except Exception as e:
            return {
                "who": "-", "policy": "-", "decision": "-",
                "target": "-", "numbers": "-", "origin": "-",
                "_error": str(e),
            }

    @staticmethod
    def _build_merged_chunks(press_releases: list[dict], related_chunks: list[dict]) -> list[dict]:
        merged: list[dict] = []
        for pr in press_releases:
            merged.append({
                "source": pr.get("source", ""),
                "date": pr.get("date", ""),
                "title": pr.get("title", ""),
                "original_text": pr.get("content_text") or pr.get("title", ""),
            })
        max_related = llm_config.max_related_chunks
        usable_related = related_chunks[:max_related] if max_related > 0 else related_chunks
        for c in usable_related:
            merged.append({
                "source": c.get("source", ""),
                "date": c.get("date", ""),
                "title": c.get("title", ""),
                "original_text": c.get("original_text") or c.get("full_text", ""),
            })
        return merged

    @staticmethod
    def _extract_model(provider: str | None, model: str | None) -> str | None:
        if provider == "bedrock" and llm_config.extract_model_id:
            return llm_config.extract_model_id
        return model

    @staticmethod
    def _apply_style_postprocess(
        article: dict,
        *,
        style: str | None,
        created_by: str | None,
    ) -> dict:
        if (style or "").lower() not in ("mediaus", "mediaus_song", "mediaus_ko"):
            return article

        reporter = (created_by or "김홍근").strip()
        reporter = re.sub(r"\s*기자\s*$", "", reporter).strip() or "김홍근"
        byline = f"[미디어스={reporter} 기자]"

        normalized = dict(article)
        normalized["lead"] = _MEDIAUS_BYLINE_RE.sub(
            "",
            str(normalized.get("lead") or ""),
        ).strip()
        body = _MEDIAUS_BYLINE_RE.sub(
            "",
            str(normalized.get("body") or ""),
        ).strip()
        normalized["body"] = f"{byline} {body}".strip()
        return normalized

    @staticmethod
    def _local_extract_json(chunks: list[dict]) -> dict:
        main = chunks[0] if chunks else {}
        text = " ".join((main.get("original_text") or "").split())
        numbers = ", ".join(
            re.findall(r"[0-9][0-9,]*(?:\.[0-9]+)?\s*(?:명|건|%|원|억원|조원|일|년|월|회|개|곳)?", text)[:8]
        )
        return {
            "who": main.get("source") or None,
            "policy": main.get("title") or None,
            "decision": text[:260] if text else main.get("title"),
            "target": None,
            "numbers": numbers or None,
            "origin": None,
            "effect": None,
            "_mode": "fast_local_extract",
        }

    @staticmethod
    def _run_with_progress(fn, *, stage: str, wait_message: str):
        started = time.monotonic()
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(fn)
            while True:
                try:
                    return future.result(timeout=_PROGRESS_INTERVAL_SECONDS)
                except TimeoutError:
                    elapsed = int(time.monotonic() - started)
                    yield {
                        "type": "stage",
                        "stage": stage,
                        "message": f"{wait_message} ({elapsed}초 경과)",
                    }

    @staticmethod
    def _stream_tokens_with_progress(draft_stream: Iterator[str]) -> Iterator[dict]:
        events: queue.Queue[tuple[str, object]] = queue.Queue()

        def produce() -> None:
            try:
                for delta in draft_stream:
                    events.put(("token", delta))
                events.put(("done", None))
            except BaseException as exc:
                events.put(("error", exc))

        threading.Thread(target=produce, daemon=True).start()
        started = time.monotonic()
        saw_token = False

        while True:
            try:
                kind, payload = events.get(timeout=_PROGRESS_INTERVAL_SECONDS)
            except queue.Empty:
                elapsed = int(time.monotonic() - started)
                if saw_token:
                    yield {
                        "type": "stage",
                        "stage": "streaming",
                        "message": f"초안을 이어 쓰는 중입니다. ({elapsed}초 경과)",
                    }
                else:
                    yield {
                        "type": "stage",
                        "stage": "drafting",
                        "message": f"모델 첫 응답을 기다리는 중입니다. ({elapsed}초 경과)",
                    }
                continue

            if kind == "token":
                if not saw_token:
                    saw_token = True
                    yield {
                        "type": "stage",
                        "stage": "streaming",
                        "message": "초안이 실시간으로 내려오고 있습니다.",
                    }
                yield {"type": "token", "delta": payload}
                continue
            if kind == "error":
                raise payload
            if kind == "done":
                return

    @staticmethod
    def _build_citations(press_releases: list[dict], related_chunks: list[dict]) -> dict[str, dict]:
        citations: dict[str, dict] = {}
        idx = 1
        for pr in press_releases:
            citations[str(idx)] = {
                "category": f"{pr.get('source', '')} 보도자료",
                "title": pr.get("title", ""),
                "date": pr.get("date", ""),
                "url": pr.get("detail_url", ""),
            }
            idx += 1
        for c in related_chunks:
            citations[str(idx)] = {
                "category": f"{c.get('source', '')} 참고기사",
                "title": c.get("title", ""),
                "date": c.get("date", ""),
                "url": c.get("detail_url") or f"#related/{c.get('chunk_id', '')}",
            }
            idx += 1
        return citations
