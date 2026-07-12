"""Build traceable Delhi DLSA contacts from a verified DSLSA snapshot."""

from __future__ import annotations

from datetime import date, datetime
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from typing import Annotated

from pydantic import Field, HttpUrl

from src.models.schemas import NonEmptyText, ShortText, StrictModel


class DirectoryError(RuntimeError):
    """A bounded directory provenance or parsing failure."""


class LegalAidContact(StrictModel):
    contact_id: Annotated[str, Field(pattern=r"^[a-z0-9_.-]+$")]
    authority: NonEmptyText
    state: ShortText
    district: ShortText | None = None
    officer_name: ShortText | None = None
    designation: NonEmptyText
    address: NonEmptyText | None = None
    phone: Annotated[str, Field(min_length=5, max_length=40)]
    email: Annotated[str, Field(min_length=3, max_length=200)]
    official_url: HttpUrl
    verified_date: date
    source_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    needs_address_review: bool = True


class LegalAidFallback(StrictModel):
    fallback_id: Annotated[str, Field(pattern=r"^[a-z0-9_.-]+$")]
    service: NonEmptyText
    scope: ShortText
    phone: Annotated[str, Field(min_length=5, max_length=40)]
    official_url: HttpUrl
    verified_date: date
    source_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    description: NonEmptyText


class _Rows(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[list[str]] = []
        self._row: list[list[str]] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs) -> None:  # type: ignore[no-untyped-def]
        if tag.casefold() == "tr":
            self._row = []
        elif tag.casefold() in {"td", "th"} and self._row is not None:
            self._cell = []
            self._row.append(self._cell)
        elif self._cell is not None and tag.casefold() in {"br", "p", "div"}:
            self._cell.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() in {"td", "th"}:
            self._cell = None
        elif tag.casefold() == "tr" and self._row is not None:
            self.rows.append([" ".join("".join(cell).split()) for cell in self._row])
            self._row = None
            self._cell = None

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)


def _verified_snapshot(path: Path, expected_source_id: str) -> tuple[str, dict[str, object]]:
    receipt_path = path.with_suffix(".html.receipt.json")
    try:
        body = path.read_bytes()
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DirectoryError("verified snapshot and receipt are required") from exc
    digest = hashlib.sha256(body).hexdigest()
    if receipt.get("source_id") != expected_source_id:
        raise DirectoryError("directory receipt source_id mismatch")
    if receipt.get("sha256") != digest or receipt.get("byte_count") != len(body):
        raise DirectoryError("directory snapshot does not match its receipt")
    return body.decode("utf-8"), receipt


def _email(value: str) -> str:
    return re.sub(r"\[dot\]", ".", re.sub(r"\[at\]", "@", value), flags=re.I)


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")


def build_delhi_contacts(snapshot_path: str | Path) -> list[LegalAidContact]:
    text, receipt = _verified_snapshot(Path(snapshot_path), "dslsa_directory")
    parser = _Rows()
    parser.feed(text)
    retrieved = datetime.fromisoformat(str(receipt["retrieved_at"]).replace("Z", "+00:00")).date()
    contacts: list[LegalAidContact] = []
    for row in parser.rows:
        if len(row) != 4:
            continue
        name, designation, email, phone = row
        match = re.search(r"Secretary,\s*(.+?)(?:,)?\s+DLSA\b", designation, re.I)
        if not match or not email or not phone:
            continue
        district = " ".join(match.group(1).split()).strip(" ,-–")
        contacts.append(
            LegalAidContact(
                contact_id=f"delhi-dlsa-{_slug(district)}",
                authority=f"{district} District Legal Services Authority",
                state="Delhi",
                district=district,
                officer_name=name,
                designation=designation,
                phone=phone,
                email=_email(email),
                official_url=str(receipt["url"]),
                verified_date=retrieved,
                source_sha256=str(receipt["sha256"]),
            )
        )
    if len(contacts) < 10:
        raise DirectoryError(f"unexpectedly small Delhi DLSA directory: {len(contacts)} contacts")
    return contacts


def build_tele_law_fallback(snapshot_path: str | Path) -> LegalAidFallback:
    text, receipt = _verified_snapshot(Path(snapshot_path), "tele_law_pib_2026")
    if "14454" not in text or "Tele-Law" not in text:
        raise DirectoryError("verified PIB snapshot does not support the Tele-Law fallback")
    retrieved = datetime.fromisoformat(str(receipt["retrieved_at"]).replace("Z", "+00:00")).date()
    return LegalAidFallback(
        fallback_id="tele-law-14454",
        service="Tele-Law",
        scope="India",
        phone="14454",
        official_url=str(receipt["url"]),
        verified_date=retrieved,
        source_sha256=str(receipt["sha256"]),
        description=(
            "Government pre-litigation legal advice through Common Service Centres, "
            "the Tele-Law mobile application, video or telephone facilities."
        ),
    )


def build_nalsa_fallback(snapshot_path: str | Path) -> LegalAidFallback:
    text, receipt = _verified_snapshot(Path(snapshot_path), "nalsa_directory")
    if "15100" not in text or "NATIONAL LEGAL SERVICES AUTHORITY" not in text:
        raise DirectoryError("verified NALSA snapshot does not support the national fallback")
    retrieved = datetime.fromisoformat(str(receipt["retrieved_at"]).replace("Z", "+00:00")).date()
    return LegalAidFallback(
        fallback_id="nalsa-15100",
        service="National Legal Services Authority helpline",
        scope="India",
        phone="15100",
        official_url=str(receipt["url"]),
        verified_date=retrieved,
        source_sha256=str(receipt["sha256"]),
        description=(
            "National legal-aid helpline and directory fallback when a verified "
            "district contact is unavailable."
        ),
    )
