"""Parse a verified NCRB Sankalan snapshot into human-review candidates."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from dataclasses import asdict, dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


class SankalanError(RuntimeError):
    """A bounded provenance or parsing failure."""


@dataclass(frozen=True, slots=True)
class SankalanCandidate:
    row_id: str
    bns_reference: str
    bns_text: str
    ipc_references: tuple[str, ...]
    ipc_text: str
    relationship_hint: str
    official_url: str
    retrieved_at: str
    sha256: str
    audit_status: str = "pending_human_review"

    def as_record(self) -> dict[str, Any]:
        return asdict(self)


class _TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[tuple[str | None, list[str]]] = []
        self._in_row = False
        self._in_cell = False
        self._row_id: str | None = None
        self._cells: list[list[str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag.casefold() == "tr":
            self._in_row = True
            self._row_id = None
            self._cells = []
        elif self._in_row and tag.casefold() == "td":
            self._in_cell = True
            self._cells.append([])
            if self._row_id is None and attributes.get("id"):
                self._row_id = attributes["id"]
        elif self._in_cell and tag.casefold() in {"br", "p", "div"} and self._cells:
            self._cells[-1].append(" ")

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() == "td":
            self._in_cell = False
        elif tag.casefold() == "tr" and self._in_row:
            cells = [_normalize("".join(parts)) for parts in self._cells]
            self.rows.append((self._row_id, cells))
            self._in_row = False
            self._in_cell = False

    def handle_data(self, data: str) -> None:
        if self._in_cell and self._cells:
            self._cells[-1].append(data)


def _normalize(value: str) -> str:
    return " ".join(value.replace("\xa0", " ").split())


def _references(value: str) -> tuple[str, ...]:
    if value.casefold() in {"new section", "new sub-section", "deleted", ""}:
        return ()
    references: list[str] = []
    for match in re.finditer(r"(?:^|\s)(\d+[A-Za-z]?(?:\(\d+\))?(?:\([a-z]\))?)\.", value):
        reference = match.group(1)
        if reference not in references:
            references.append(reference)
    return tuple(references)


def _hint(ipc_text: str, ipc_references: tuple[str, ...]) -> str:
    lowered = ipc_text.casefold()
    if "new section" in lowered or "new sub-section" in lowered:
        return "new_in_bns"
    if "deleted" in lowered:
        return "deleted_or_omitted"
    if len(ipc_references) > 1:
        return "possible_merge"
    if len(ipc_references) == 1:
        return "corresponding_provision"
    return "requires_review"


def parse_verified_sankalan(snapshot_path: str | Path) -> list[SankalanCandidate]:
    path = Path(snapshot_path)
    receipt_path = path.with_suffix(".html.receipt.json")
    try:
        body = path.read_bytes()
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SankalanError("snapshot and valid receipt are required") from exc
    digest = hashlib.sha256(body).hexdigest()
    if receipt.get("source_id") != "ncrb_sankalan_ipc_bns":
        raise SankalanError("receipt source_id does not identify the reviewed Sankalan table")
    if receipt.get("sha256") != digest or receipt.get("byte_count") != len(body):
        raise SankalanError("snapshot bytes do not match the download receipt")
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SankalanError("Sankalan snapshot must be UTF-8") from exc
    parser = _TableParser()
    parser.feed(text)
    candidates: list[SankalanCandidate] = []
    for row_id, cells in parser.rows:
        if not row_id or len(cells) != 2 or not cells[0]:
            continue
        ipc_refs = _references(cells[1])
        candidates.append(
            SankalanCandidate(
                row_id=row_id,
                bns_reference=row_id.replace(".", "(", 1) + (")" if "." in row_id else ""),
                bns_text=cells[0],
                ipc_references=ipc_refs,
                ipc_text=cells[1],
                relationship_hint=_hint(cells[1], ipc_refs),
                official_url=receipt["url"],
                retrieved_at=receipt["retrieved_at"],
                sha256=digest,
            )
        )
    if len(candidates) < 300:
        raise SankalanError(f"unexpectedly small Sankalan table: {len(candidates)} rows")
    return candidates


def write_candidates(candidates: list[SankalanCandidate], output_path: str | Path) -> None:
    path = Path(output_path)
    data = "".join(
        json.dumps(item.as_record(), ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        for item in candidates
    ).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise
