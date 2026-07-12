"""Dependency-light command-line entry point for the first implementation milestone."""

from __future__ import annotations

import argparse
from datetime import date
import json
from pathlib import Path
from typing import Any, Sequence

from src.config import Settings
from src.retrieval import HybridRetriever, RetrievalDocument, SearchFilters


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FIXTURE = PROJECT_ROOT / "fixtures" / "retrieval_corpus.json"


def load_documents(path: Path) -> tuple[RetrievalDocument, ...]:
    """Load a small JSON corpus while preserving every provenance field."""

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"Corpus file does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Corpus file contains invalid JSON: {path}") from exc
    if not isinstance(payload, list):
        raise ValueError("Corpus JSON must be a list of source records")

    documents: list[RetrievalDocument] = []
    for index, item in enumerate(payload):
        if not isinstance(item, dict):
            raise ValueError(f"Corpus item {index} must be an object")
        source_id = item.get("source_id")
        body = item.get("text")
        if not isinstance(source_id, str) or not isinstance(body, str):
            raise ValueError(f"Corpus item {index} requires string source_id and text")
        metadata: dict[str, Any] = {key: value for key, value in item.items() if key != "text"}
        # Index citation-bearing labels as well as body text. The original body remains
        # available in metadata for later source conversion.
        searchable = " ".join(
            str(value)
            for value in (
                item.get("act", ""),
                item.get("section", ""),
                item.get("heading", ""),
                body,
            )
            if value
        )
        metadata["source_text"] = body
        documents.append(
            RetrievalDocument(source_id=source_id, text=searchable, metadata=metadata)
        )
    return tuple(documents)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nyaya",
        description="Offline retrieval smoke test. The bundled corpus is synthetic only.",
    )
    parser.add_argument("--query", required=True, help="Text to retrieve from the local fixture")
    parser.add_argument("--corpus", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--jurisdiction")
    parser.add_argument("--language")
    parser.add_argument("--act")
    parser.add_argument("--status")
    parser.add_argument("--document-type")
    parser.add_argument("--effective-on", type=date.fromisoformat)
    parser.add_argument("--limit", type=int, default=5)
    return parser


def run(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.limit <= 0:
        raise SystemExit("--limit must be positive")

    settings = Settings.from_env()
    documents = load_documents(args.corpus)
    retriever = HybridRetriever(documents)
    filters = SearchFilters(
        jurisdiction=args.jurisdiction,
        language=args.language,
        act=args.act,
        status=args.status,
        document_type=args.document_type,
        effective_on=args.effective_on,
    )
    results = retriever.search(args.query, limit=args.limit, filters=filters)

    print("NYAYA NAVIGATOR — SYNTHETIC RETRIEVAL SMOKE TEST")
    print("This output is not legal information and does not use the production corpus.")
    print(f"Configured local model: {settings.ollama_model} at {settings.ollama_url}")
    if not results:
        print("No local fixture result matched.")
        return 1
    for result in results:
        metadata = result.metadata
        print(
            f"{result.rank}. {metadata.get('act')} § {metadata.get('section')} "
            f"[{metadata.get('status')}] score={result.score:.6f}"
        )
        print(f"   source_id={result.source_id}")
        print(f"   {metadata.get('source_text')}")
    return 0


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
