"""Precompute and persist local embedding vectors for the reviewed corpus.

Runs entirely against the loopback Ollama runtime. No corpus text leaves the
device. Vectors are cached by embedding model and text hash, so re-running after
a partial corpus rebuild only embeds what actually changed.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import Sequence

from src.agents.ollama import OllamaError
from src.models.schemas import LegalDomain
from src.retrieval import CorpusLoadError, load_processed_corpus
from src.retrieval.collections import CollectionError, collection_for_domain
from src.retrieval.embeddings import DEFAULT_EMBEDDING_MODEL, LocalEmbedder


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="build_index",
        description="Precompute EmbeddingGemma vectors for the reviewed corpus.",
    )
    parser.add_argument("--sections-dir", type=Path, default=Path("data/processed/sections"))
    parser.add_argument("--cache-dir", type=Path, default=Path("data/indexes"))
    parser.add_argument("--model", default=DEFAULT_EMBEDDING_MODEL)
    parser.add_argument(
        "--domain",
        action="append",
        choices=[item.value for item in LegalDomain],
        help="Restrict to one or more domains; defaults to every routed domain.",
    )
    return parser


def run(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        documents = load_processed_corpus(args.sections_dir)
    except CorpusLoadError as exc:
        print(f"corpus unavailable: {exc}", file=sys.stderr)
        return 1

    domains = (
        [LegalDomain(value) for value in args.domain]
        if args.domain
        else [item for item in LegalDomain if item is not LegalDomain.OTHER]
    )
    embedder = LocalEmbedder(model=args.model, cache_dir=args.cache_dir)
    print(f"corpus: {len(documents)} chunks | model: {args.model}")

    total = 0
    for domain in domains:
        try:
            scoped = collection_for_domain(documents, domain)
        except CollectionError as exc:
            print(f"  {domain.value:20} skipped: {exc}")
            continue
        started = time.perf_counter()
        try:
            embedder([document.text for document in scoped])
        except OllamaError as exc:
            print(f"local embedding runtime failed: {exc}", file=sys.stderr)
            return 1
        total += len(scoped)
        print(
            f"  {domain.value:20} {len(scoped):5} chunks  "
            f"{time.perf_counter() - started:6.1f}s"
        )

    embedder.save()
    if embedder.cache_path.is_file():
        size = embedder.cache_path.stat().st_size // 1024
        print(f"cache: {embedder.cache_path} ({size} KiB, {total} chunks embedded)")
    return 0


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
