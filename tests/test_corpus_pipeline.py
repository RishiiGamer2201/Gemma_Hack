from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from scripts.build_corpus import main as build_cli
from src.corpus.pipeline import CorpusBuildError, build_corpus


DOWNLOADED_AT = "2026-07-12T09:30:00+00:00"


class PipelineFixture:
    def __init__(self, root: Path, *, required: bool = True) -> None:
        self.root = root
        self.raw = root / "raw"
        self.output = root / "output"
        self.raw.mkdir()
        self.manifest = root / "manifest.json"
        self.source_id = "synthetic_act_en"
        self.filename = "synthetic_act.txt"
        self.body = (
            "THE SYNTHETIC ACT\nBe it enacted\n1. First right\nPage one body"
            "\fContinuation on page two\n2. Second right\nPage two body"
        ).encode("utf-8")
        source = {
            "source_id": self.source_id,
            "title": "The Synthetic Act",
            "url": "https://law.gov.in/files/synthetic_act.txt",
            "official_landing_url": "https://law.gov.in/acts/synthetic",
            "filename": self.filename,
            "language": "en",
            "jurisdiction": "India",
            "document_type": "act",
            "effective_from": "2024-07-01",
            "effective_to": None,
            "status": "in_force",
            "priority": 1,
            "parser": "text",
            "required": required,
            "allowed_hosts": ["law.gov.in"],
        }
        self.manifest.write_text(
            json.dumps({"schema_version": 1, "sources": [source]}), encoding="utf-8"
        )

    @property
    def source_path(self) -> Path:
        return self.raw / self.filename

    @property
    def receipt_path(self) -> Path:
        return self.raw / f"{self.filename}.receipt.json"

    def install_verified_artifact(self) -> None:
        self.source_path.write_bytes(self.body)
        digest = hashlib.sha256(self.body).hexdigest()
        self.receipt_path.write_text(
            json.dumps(
                {
                    "source_id": self.source_id,
                    "filename": self.filename,
                    "url": "https://law.gov.in/files/synthetic_act.txt",
                    "official_landing_url": "https://law.gov.in/acts/synthetic",
                    "downloaded_at": DOWNLOADED_AT,
                    "byte_count": len(self.body),
                    "sha256": digest,
                    "content_type": "text/plain",
                }
            ),
            encoding="utf-8",
        )


class CorpusPipelineTests(unittest.TestCase):
    def test_valid_text_build_preserves_provenance_and_audit_fields(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = PipelineFixture(Path(directory))
            fixture.install_verified_artifact()
            report = build_corpus(fixture.manifest, fixture.raw, fixture.output)
            records = [
                json.loads(line)
                for line in (fixture.output / f"{fixture.source_id}.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
            ]

        self.assertEqual(report.required_failures, 0)
        self.assertEqual(report.successes[0].page_count, 2)
        first_section = next(record for record in records if record["section_id"] == "1")
        self.assertEqual((first_section["page_start"], first_section["page_end"]), (1, 2))
        metadata = first_section["metadata"]
        self.assertEqual(metadata["official_url"], "https://law.gov.in/files/synthetic_act.txt")
        self.assertEqual(metadata["retrieved_at"], DOWNLOADED_AT)
        self.assertEqual(metadata["effective_from"], "2024-07-01")
        self.assertEqual(metadata["audit_status"], "pending_human_review")
        self.assertFalse(metadata["ocr_used"])
        self.assertEqual(metadata["parser"], "text")

    def test_tampered_source_bytes_are_rejected_by_receipt_digest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = PipelineFixture(Path(directory))
            fixture.install_verified_artifact()
            fixture.source_path.write_bytes(fixture.body + b"tampered")
            report = build_corpus(fixture.manifest, fixture.raw, fixture.output)

        self.assertEqual(report.required_failures, 1)
        self.assertIn("SHA-256 does not match", report.failures[0].error)
        self.assertEqual(report.successes, ())

    def test_receipt_identity_and_byte_count_mismatches_are_rejected(self) -> None:
        for field, value, expected in (
            ("source_id", "different", "source_id does not match"),
            ("filename", "different.txt", "filename does not match"),
            ("url", "https://law.gov.in/files/other.txt", "url does not match"),
            (
                "official_landing_url",
                "https://law.gov.in/acts/other",
                "official_landing_url does not match",
            ),
            ("byte_count", 1, "byte_count does not match"),
        ):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                fixture = PipelineFixture(Path(directory))
                fixture.install_verified_artifact()
                receipt = json.loads(fixture.receipt_path.read_text(encoding="utf-8"))
                receipt[field] = value
                fixture.receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
                report = build_corpus(fixture.manifest, fixture.raw, fixture.output)
                self.assertEqual(report.required_failures, 1)
                self.assertIn(expected, report.failures[0].error)

    def test_failed_rebuild_removes_stale_source_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = PipelineFixture(Path(directory))
            fixture.install_verified_artifact()
            build_corpus(fixture.manifest, fixture.raw, fixture.output)
            output_path = fixture.output / f"{fixture.source_id}.jsonl"
            self.assertTrue(output_path.is_file())

            fixture.source_path.write_bytes(fixture.body + b"tampered")
            report = build_corpus(fixture.manifest, fixture.raw, fixture.output)

            self.assertEqual(report.required_failures, 1)
            self.assertFalse(output_path.exists())

    def test_missing_required_source_is_reported_and_cli_returns_one(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = PipelineFixture(Path(directory), required=True)
            error = io.StringIO()
            output = io.StringIO()
            with redirect_stderr(error), redirect_stdout(output):
                exit_code = build_cli(
                    [
                        "--manifest", str(fixture.manifest),
                        "--raw-dir", str(fixture.raw),
                        "--output-dir", str(fixture.output),
                    ]
                )
            stored_report = json.loads(
                (fixture.output / "build_report.json").read_text(encoding="utf-8")
            )

        self.assertEqual(exit_code, 1)
        self.assertIn("source file is missing", error.getvalue())
        self.assertEqual(stored_report["summary"]["required_failures"], 1)

    def test_missing_optional_source_does_not_make_cli_nonzero(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = PipelineFixture(Path(directory), required=False)
            with redirect_stderr(io.StringIO()), redirect_stdout(io.StringIO()):
                exit_code = build_cli(
                    [
                        "--manifest", str(fixture.manifest),
                        "--raw-dir", str(fixture.raw),
                        "--output-dir", str(fixture.output),
                    ]
                )
        self.assertEqual(exit_code, 0)

    def test_unknown_source_id_is_bounded_error_and_cli_returns_two(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fixture = PipelineFixture(Path(directory))
            with self.assertRaisesRegex(CorpusBuildError, "unknown source_id"):
                build_corpus(
                    fixture.manifest,
                    fixture.raw,
                    fixture.output,
                    source_ids=["unknown"],
                )
            error = io.StringIO()
            with redirect_stderr(error):
                exit_code = build_cli(
                    [
                        "--manifest", str(fixture.manifest),
                        "--raw-dir", str(fixture.raw),
                        "--output-dir", str(fixture.output),
                        "--source-id", "unknown",
                    ]
                )

        self.assertEqual(exit_code, 2)
        self.assertIn("unknown source_id", error.getvalue())

    def test_repeated_builds_are_byte_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fixture = PipelineFixture(root)
            fixture.install_verified_artifact()
            first_output = root / "first"
            second_output = root / "second"
            first = build_corpus(fixture.manifest, fixture.raw, first_output)
            second = build_corpus(fixture.manifest, fixture.raw, second_output)

            self.assertEqual(first.as_record(), second.as_record())
            self.assertEqual(
                (first_output / f"{fixture.source_id}.jsonl").read_bytes(),
                (second_output / f"{fixture.source_id}.jsonl").read_bytes(),
            )
            self.assertEqual(
                (first_output / "build_report.json").read_bytes(),
                (second_output / "build_report.json").read_bytes(),
            )


if __name__ == "__main__":
    unittest.main()
