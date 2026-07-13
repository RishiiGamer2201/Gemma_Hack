"""Download revision-pinned public evaluation datasets with local receipts."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path, PurePath
from typing import Any


def _load_manifest(path: Path) -> list[dict[str, str]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1 or not isinstance(payload.get("datasets"), list):
        raise ValueError("unsupported public dataset manifest")
    records: list[dict[str, str]] = []
    seen: set[str] = set()
    for raw in payload["datasets"]:
        if not isinstance(raw, dict):
            raise ValueError("dataset records must be objects")
        required = ("dataset_id", "repository", "revision", "output_directory", "purpose")
        if any(not isinstance(raw.get(key), str) or not raw[key].strip() for key in required):
            raise ValueError("dataset record has a missing or invalid required field")
        dataset_id = raw["dataset_id"]
        if dataset_id in seen:
            raise ValueError(f"duplicate dataset_id: {dataset_id}")
        seen.add(dataset_id)
        if PurePath(raw["output_directory"]).name != raw["output_directory"]:
            raise ValueError("output_directory must be a safe basename")
        revision = raw["revision"]
        if len(revision) != 40 or any(char not in "0123456789abcdef" for char in revision):
            raise ValueError("revision must be a lowercase 40-character commit SHA")
        records.append({key: raw[key] for key in required})
    return records


def _hash_files(root: Path) -> tuple[list[dict[str, Any]], int]:
    files: list[dict[str, Any]] = []
    total = 0
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        if (
            not path.is_file()
            or ".cache" in path.parts
            or ".git" in path.parts
            or path.name == "download_receipt.json"
        ):
            continue
        digest = hashlib.sha256()
        size = 0
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
                size += len(block)
        total += size
        files.append(
            {
                "path": path.relative_to(root).as_posix(),
                "byte_count": size,
                "sha256": digest.hexdigest(),
            }
        )
    return files, total


def _write_receipt(root: Path, record: dict[str, str]) -> None:
    files, byte_count = _hash_files(root)
    receipt = {
        **record,
        "retrieved_at": datetime.now(UTC).isoformat(),
        "file_count": len(files),
        "byte_count": byte_count,
        "files": files,
    }
    (root / "download_receipt.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("config/public_datasets.json"))
    parser.add_argument("--output-root", type=Path, default=Path("data/raw/benchmarks"))
    parser.add_argument("--dataset-id", action="append", dest="dataset_ids")
    parser.add_argument("--list", action="store_true", help="validate and list without network access")
    parser.add_argument(
        "--verify-existing",
        action="store_true",
        help="hash an already downloaded revision without making network requests",
    )
    args = parser.parse_args(argv)

    try:
        records = _load_manifest(args.manifest)
        if args.dataset_ids:
            requested = set(args.dataset_ids)
            known = {record["dataset_id"] for record in records}
            unknown = sorted(requested - known)
            if unknown:
                raise ValueError("unknown dataset_id value(s): " + ", ".join(unknown))
            records = [record for record in records if record["dataset_id"] in requested]
        if args.list:
            for record in records:
                print(f"{record['dataset_id']}\t{record['repository']}@{record['revision']}")
            return 0

        snapshot_download = None
        if not args.verify_existing:
            from huggingface_hub import snapshot_download as hub_snapshot_download

            snapshot_download = hub_snapshot_download

        for record in records:
            destination = args.output_root / record["output_directory"]
            if args.verify_existing and not destination.is_dir():
                raise ValueError(f"existing dataset directory is missing: {destination}")
            destination.mkdir(parents=True, exist_ok=True)
            if not args.verify_existing:
                assert snapshot_download is not None
                try:
                    snapshot_download(
                        repo_id=record["repository"],
                        repo_type="dataset",
                        revision=record["revision"],
                        local_dir=destination,
                        max_workers=1,
                    )
                except Exception as exc:
                    raise RuntimeError(
                        f"dataset download failed for {record['dataset_id']}: {exc}"
                    ) from exc
            _write_receipt(destination, record)
            action = "VERIFIED" if args.verify_existing else "DOWNLOADED"
            print(f"{action} {record['dataset_id']} -> {destination}")
        return 0
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
