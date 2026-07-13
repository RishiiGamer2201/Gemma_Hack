"""End-to-end answer evaluation: the metrics the plan actually asks for.

Runs the real pipeline against the real model and reports:

* fabricated citations       -- claims citing a source that was never retrieved
* unsupported-claim rate     -- claims shown to a user that the verifier did not support
* citation precision         -- shown claims that carry a verified source
* correct act rate           -- published answers citing the expected Act
* abstention accuracy        -- did it refuse / route / ask exactly when it should
* end-to-end latency         -- what a person waits, on this machine

The first two are the ones that matter. The system is built so that a claim which
fails verification is never published, so both should be ZERO -- and if they are
not, that is a hole in the safety story, not a tuning problem.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

from src.agents.ollama import OllamaClient, OllamaError
from src.config import Settings
from src.intake import UrgencyCategory
from src.models.schemas import ClaimVerdict, ConfirmedFacts
from src.pipeline import run_confirmed_request
from src.retrieval import CorpusLoadError, load_processed_corpus
from src.retrieval.collections import collection_for_domain
from src.retrieval.embeddings import LocalEmbedder
from src.safety.models import RoutePriority

# What the observed run must look like for each expected behaviour.
_EXPECTED = {
    "published": lambda result: result.published,
    "refused": lambda result: result.route.priority is RoutePriority.HARD_ABSTAIN,
    "urgent": lambda result: result.route.priority is RoutePriority.IMMEDIATE_HUMAN_HELP,
    "needs_information": lambda result: result.route.priority
    is RoutePriority.NEEDS_INFORMATION,
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="evaluate_answers",
        description="Measure citation precision, unsupported claims, abstention, latency.",
    )
    parser.add_argument("--scenarios", type=Path, default=Path("fixtures/answer_scenarios.json"))
    parser.add_argument("--sections-dir", type=Path, default=Path("data/processed/sections"))
    parser.add_argument("--limit", type=int, default=4)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--no-embeddings", action="store_true")
    return parser


def run(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        payload = json.loads(args.scenarios.read_text(encoding="utf-8"))
        documents = load_processed_corpus(args.sections_dir)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"could not read the scenarios: {exc}", file=sys.stderr)
        return 1
    except CorpusLoadError as exc:
        print(f"corpus unavailable: {exc}", file=sys.stderr)
        return 1

    settings = Settings.from_env()
    client = OllamaClient(settings.ollama_url, timeout=600.0)
    embedder = None if args.no_embeddings else LocalEmbedder(client)

    scenarios = payload["scenarios"]
    rows: list[dict] = []
    fabricated = 0
    unsupported = 0
    shown_claims = 0
    verified_claims = 0
    correct_act = 0
    act_checked = 0
    behaved = 0
    latencies: list[float] = []
    # A refused or urgent case short-circuits before the model runs, so an
    # overall median is ~0 and tells a reader nothing. What a person actually
    # waits for is a published answer.
    answer_latencies: list[float] = []

    for scenario in scenarios:
        facts = ConfirmedFacts.model_validate(
            {
                **scenario["facts"],
                "confirmed": True,
                "confirmed_at": datetime.now(UTC).isoformat(),
            }
        )
        scoped = collection_for_domain(documents, facts.domain)
        started = time.perf_counter()
        try:
            result = run_confirmed_request(
                facts,
                scoped,
                client=client,
                model=settings.ollama_model,
                confirmed_urgencies=[
                    UrgencyCategory(value)
                    for value in scenario.get("confirmed_urgencies", [])
                ],
                requested_output=scenario.get("requested_output"),
                evidence_limit=args.limit,
                embedding_callback=embedder,
            )
        except OllamaError as exc:
            print(f"{scenario['id']}: local model failed: {exc}", file=sys.stderr)
            return 1
        elapsed = time.perf_counter() - started
        latencies.append(elapsed)
        if result.published:
            answer_latencies.append(elapsed)

        expected = scenario["expect"]
        ok = _EXPECTED[expected](result)
        behaved += ok

        retrieved = (
            {item.source_id for item in result.evidence_bundle.evidence}
            if result.evidence_bundle
            else set()
        )
        acts = (
            {item.act for item in result.evidence_bundle.evidence}
            if result.evidence_bundle
            else set()
        )

        # Only claims actually SHOWN to a user count. A withheld answer harms nobody.
        if result.published and result.answer is not None:
            verdicts = {item.claim_id: item for item in result.verifications}
            for claim in result.answer.claims:
                shown_claims += 1
                if any(source not in retrieved for source in claim.cited_source_ids):
                    fabricated += 1
                verdict = verdicts.get(claim.claim_id)
                if verdict is None or verdict.verdict is not ClaimVerdict.SUPPORTED:
                    unsupported += 1
                else:
                    verified_claims += 1

            if scenario.get("expected_acts"):
                act_checked += 1
                correct_act += any(
                    expected_act in acts for expected_act in scenario["expected_acts"]
                )

        rows.append(
            {
                "id": scenario["id"],
                "expected": expected,
                "observed": result.route.priority.value
                if not result.published
                else "published",
                "as_expected": bool(ok),
                "stage": result.stage.value,
                "claims": len(result.claims) if hasattr(result, "claims") else 0,
                "seconds": round(elapsed, 1),
            }
        )
        mark = "ok " if ok else "FAIL"
        print(
            f"{mark} {scenario['id']:26} expected={expected:17} "
            f"stage={result.stage.value:14} {elapsed:6.1f}s"
        )

    total = len(scenarios)
    print()
    print(f"{'metric':32} {'value':>10}")
    print(f"{'fabricated citations':32} {fabricated:>10}")
    print(f"{'unsupported claims shown':32} {unsupported:>10}")
    print(
        f"{'unsupported-claim rate':32} "
        f"{(unsupported / shown_claims if shown_claims else 0):>10.3f}"
    )
    print(
        f"{'citation precision':32} "
        f"{(verified_claims / shown_claims if shown_claims else 0):>10.3f}"
    )
    print(
        f"{'correct act rate':32} "
        f"{(correct_act / act_checked if act_checked else 0):>10.3f}"
    )
    print(f"{'abstention/route accuracy':32} {behaved / total:>10.3f}")
    if answer_latencies:
        print(
            f"{'median answer latency (s)':32} "
            f"{statistics.median(answer_latencies):>10.1f}"
        )
        print(f"{'max answer latency (s)':32} {max(answer_latencies):>10.1f}")
    print(
        f"{'median latency, all cases (s)':32} {statistics.median(latencies):>10.1f}"
    )

    if fabricated or unsupported:
        print()
        print(
            "FAILED: a claim reached a user without verified support. This is a hole "
            "in the safety story, not a tuning problem."
        )

    if payload.get("review_status") != "reviewed":
        print()
        print(
            "NOT CERTIFIED: these scenarios have not been independently reviewed. "
            "Phase L requires a reviewer other than the author."
        )

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(
                {
                    "review_status": payload.get("review_status"),
                    "scenarios": rows,
                    "metrics": {
                        "fabricated_citations": fabricated,
                        "unsupported_claims_shown": unsupported,
                        "shown_claims": shown_claims,
                        "unsupported_claim_rate": round(
                            unsupported / shown_claims if shown_claims else 0, 4
                        ),
                        "citation_precision": round(
                            verified_claims / shown_claims if shown_claims else 0, 4
                        ),
                        "correct_act_rate": round(
                            correct_act / act_checked if act_checked else 0, 4
                        ),
                        "route_accuracy": round(behaved / total, 4),
                        "median_answer_latency_seconds": round(
                            statistics.median(answer_latencies), 1
                        )
                        if answer_latencies
                        else None,
                        "max_answer_latency_seconds": round(max(answer_latencies), 1)
                        if answer_latencies
                        else None,
                        "median_latency_all_cases_seconds": round(
                            statistics.median(latencies), 1
                        ),
                    },
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        print(f"wrote {args.output}")
    return 0 if not (fabricated or unsupported) else 2


def main() -> None:
    raise SystemExit(run())


if __name__ == "__main__":
    main()
