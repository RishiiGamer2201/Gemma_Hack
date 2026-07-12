from __future__ import annotations

from email.message import Message
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.corpus.downloader import DownloadError, download_source
from src.corpus.manifest import OfficialSource

from tests.test_corpus_manifest import source_payload


class FakeResponse:
    def __init__(
        self,
        body: bytes,
        *,
        url: str = "https://law.gov.in/files/act.pdf",
        content_type: str = "application/pdf",
        content_length: str | None = None,
    ) -> None:
        self.body = body
        self.url = url
        self.headers = Message()
        self.headers["Content-Type"] = content_type
        if content_length is not None:
            self.headers["Content-Length"] = content_length

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def geturl(self) -> str:
        return self.url

    def read(self, limit: int) -> bytes:
        return self.body[:limit]


class FakeOpener:
    def __init__(self, response: FakeResponse) -> None:
        self.response = response
        self.requests: list[object] = []

    def open(self, request: object, *, timeout: float) -> FakeResponse:
        self.requests.append(request)
        return self.response


def source(**updates: object) -> OfficialSource:
    return OfficialSource.model_validate(source_payload(**updates))


class DownloaderTests(unittest.TestCase):
    def _download(self, response: FakeResponse, directory: str, **kwargs: object):
        opener = FakeOpener(response)
        with patch("src.corpus.downloader.build_opener", return_value=opener):
            receipt = download_source(source(), directory, **kwargs)
        return receipt, opener

    def test_negative_content_length_is_rejected(self) -> None:
        response = FakeResponse(b"%PDF-1.7\nsynthetic", content_length="-1")
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(DownloadError, "negative Content-Length"):
                self._download(response, directory)

    def test_success_writes_verified_payload_checksum_and_receipt(self) -> None:
        body = b"%PDF-1.7\nsynthetic"
        with tempfile.TemporaryDirectory() as directory:
            receipt, opener = self._download(FakeResponse(body), directory)
            destination = Path(directory) / "synthetic_act.pdf"
            digest = hashlib.sha256(body).hexdigest()
            self.assertEqual(destination.read_bytes(), body)
            self.assertEqual(
                destination.with_suffix(".pdf.sha256").read_text(encoding="ascii"),
                f"{digest}  synthetic_act.pdf\n",
            )
            stored = json.loads(
                destination.with_suffix(".pdf.receipt.json").read_text(encoding="utf-8")
            )
            self.assertEqual(stored["sha256"], digest)
            self.assertEqual(stored["byte_count"], len(body))
            self.assertEqual(receipt.sha256, digest)
            self.assertEqual(len(opener.requests), 1)

    def test_redirected_response_is_blocked_before_writing(self) -> None:
        response = FakeResponse(b"%PDF-1.7\n", url="https://law.gov.in/other.pdf")
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(DownloadError, "redirected"):
                self._download(response, directory)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_pdf_content_type_and_magic_are_both_required(self) -> None:
        cases = (
            FakeResponse(b"%PDF-1.7\n", content_type="text/html"),
            FakeResponse(b"<html>not a pdf</html>", content_type="application/pdf"),
        )
        for response in cases:
            with self.subTest(content_type=response.headers.get_content_type()):
                with tempfile.TemporaryDirectory() as directory:
                    with self.assertRaises(DownloadError):
                        self._download(response, directory)
                    self.assertEqual(list(Path(directory).iterdir()), [])

    def test_declared_and_streamed_size_limits_are_enforced(self) -> None:
        cases = (
            FakeResponse(b"%PDF-", content_length="100"),
            FakeResponse(b"%PDF-123456789"),
        )
        for response in cases:
            with self.subTest(declared=response.headers.get("Content-Length")):
                with tempfile.TemporaryDirectory() as directory:
                    with self.assertRaisesRegex(DownloadError, "byte limit"):
                        self._download(response, directory, max_bytes=8)

    def test_invalid_content_length_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(DownloadError, "invalid Content-Length"):
                self._download(
                    FakeResponse(b"%PDF-1.7", content_length="not-an-integer"), directory
                )

    def test_existing_payload_or_sidecar_prevents_network_and_clobber(self) -> None:
        for existing_name in (
            "synthetic_act.pdf",
            "synthetic_act.pdf.sha256",
            "synthetic_act.pdf.receipt.json",
        ):
            with self.subTest(existing_name=existing_name):
                with tempfile.TemporaryDirectory() as directory:
                    path = Path(directory) / existing_name
                    path.write_bytes(b"keep")
                    opener = FakeOpener(FakeResponse(b"%PDF-1.7"))
                    with patch("src.corpus.downloader.build_opener", return_value=opener):
                        with self.assertRaises(FileExistsError):
                            download_source(source(), directory)
                    self.assertEqual(path.read_bytes(), b"keep")
                    self.assertEqual(opener.requests, [])

    def test_text_download_accepts_only_documented_content_types(self) -> None:
        text_source = source(
            url="https://law.gov.in/files/act.txt",
            filename="synthetic_act.txt",
            parser="text",
        )
        with tempfile.TemporaryDirectory() as directory:
            opener = FakeOpener(FakeResponse(b"hello", url=text_source.url, content_type="text/plain"))
            with patch("src.corpus.downloader.build_opener", return_value=opener):
                receipt = download_source(text_source, directory)
            self.assertEqual(receipt.content_type, "text/plain")


if __name__ == "__main__":
    unittest.main()
