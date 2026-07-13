"""Measure retrieval quality: BM25-only vs vector-only vs hybrid.

Runs entirely on device against the reviewed corpus and the local embedding
runtime. Reports Recall@k and MRR per system, so the hybrid design can be compared
against BOTH baselines the plan requires, not just the lexical one.

The bundled query set was written by the implementer and is marked
`pending_independent_review`. Phase L requires an independent reviewer before these
numbers may be quoted anywhere. The script prints that status with the results so a
provisional number cannot be mistaken for a certified one.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from src.agents.ollama import OllamaError
from src.models.schemas import LegalDomain
from src.retrieval import CorpusLoadError, HybridRetriever, load_processed_corpus
from src.retrieval.collections import CollectionError, collection_for_domain
from src.retrieval.embeddings import LocalEmbedder

SYSTEMS = ("bm25", "vector", "hybrid")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="evaluate_retrieval",
        description="Compare BM25-only, vector-only, and hybrid retrieval.",
    )
    parser.add_argument("--queries", type=Path, default=Path("fixtures/eval_queries.json"))
    parser.add_argument("--sections-dir", type=Path, default=Path("data/processed/sections"))
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--output", type=Path, help="Write the full result as JSON.")
    return parser


def _retriever(scoped, system: str, embedder) -> HybridRetriever:  # noqa: ANN001
    if system == "bm25":
        return HybridRetriever(scoped, embedding_weight=0.0, embedding_version_key="bm25")
    if system == "vector":
        # bm25_weight=0 disables the lexical channel entirely, giving a true
        # vector-only baseline rather than a lexically-assisted one.
        return HybridRetriever(
            scoped,
            embedding_callback=embedder,
            bm25_weight=0.0,
            embedding_version_key="embeddinggemma",
        )
    return HybridRetriever(
        scoped, embedding_callback=embedder, embedding_version_key="embeddinggemma"
    )


def run(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        payload = json.loads(args.queries.read_text(encoding="utf-8"))
        documents = load_processed_corpus(args.sections_dir)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"could not read the query set: {exc}", file=sys.stderr)
        return 1
    except CorpusLoadError as exc:
        print(f"corpus unavailable: {exc}", file=sys.stderr)
        return 1

    queries = payload["queries"]
    review_status = payload.get("review_status", "unknown")
    embedder = LocalEmbedder()

    results: dict[str, dict[str, float]] = {}
    misses: dict[str, list[str]] = {system: [] for system in SYSTEMS}

    for system in SYSTEMS:
        hits = 0
        reciprocal = 0.0
        cache: dict[str, HybridRetriever] = {}
        for item in queries:
            domain = LegalDomain(item["domain"])
            if domain.value not in cache:
                try:
                    scoped = collection_for_domain(documents, domain)
                except CollectionError as exc:
                    print(f"  {item['id']}: {exc}", file=sys.stderr)
                    continue
                try:
                    cache[domain.value] = _retriever(scoped, system, embedder)
                except OllamaError as exc:
                    print(f"local embedding runtime failed: {exc}", file=sys.stderr)
                    return 1
            found = [
                result.source_id
                for result in cache[domain.value].search(item["query"], limit=args.k)
            ]
            accepted = {item["expected"], *item.get("also_acceptable", [])}
            rank = next(
                (index for index, source in enumerate(found, start=1) if source in accepted),
                None,
            )
            if rank is None:
                misses[system].append(item["id"])
            else:
                hits += 1
                reciprocal += 1 / rank
        total = len(queries)
        results[system] = {
            f"recall@{args.k}": round(hits / total, 3) if total else 0.0,
            "mrr": round(reciprocal / total, 3) if total else 0.0,
        }

    print(f"queries: {len(queries)} | k: {args.k} | review status: {review_status}")
    print()
    print(f"{'system':10} {'recall@' + str(args.k):>10} {'MRR':>8}")
    for system in SYSTEMS:
        row = results[system]
        print(f"{system:10} {row[f'recall@{args.k}']:>10.3f} {row['mrr']:>8.3f}")
    print()
    for system in SYSTEMS:
        if misses[system]:
            print(f"{system} missed: {', '.join(misses[system])}")

    if review_status != "reviewed":
        print()
        print(
            "NOT CERTIFIED: this query set has not been independently reviewed. "
            "Phase L requires a reviewer other than the author before these numbers "
            "are quoted."
        )

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(
                {
                    "k": args.k,
                    "query_count": len(queries),
                    "review_status": review_status,
                    "results": results,
                    "misses": misses,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"wrote {args.output}")
    return 0


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
