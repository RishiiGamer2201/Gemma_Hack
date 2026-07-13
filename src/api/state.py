"""Process-local, in-memory caches for the loopback API.

Nothing here persists user content. The only cached data is the reviewed, on-disk
corpus and the reviewed local directories/catalogues that ship with the build.

The processed corpus is large (thousands of chunks) and must be loaded once at
startup. Per-domain scoped collections are derived lazily and cached, so a request
never re-scans the full corpus.
"""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass, field
from pathlib import Path

from src.actions.checklists import ChecklistCatalog, ChecklistError
from src.config import Settings
from src.legal_aid.finder import LegalAidFinder, LegalAidFinderError
from src.legal_time.mapping import MappingCatalog
from src.models.schemas import LegalDomain
from src.ocr import DEFAULT_TESSERACT_PATH, OCRConfig, OCRLanguage
from src.retrieval import CorpusLoadError, RetrievalDocument, corpus_sha256, load_processed_corpus
from src.retrieval.collections import CollectionError, collection_for_domain

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_CORPUS_DIR = ROOT / "data" / "processed" / "sections"
DEFAULT_CONTACTS_PATH = ROOT / "data" / "processed" / "contacts" / "delhi_dlsa.json"
DEFAULT_CHECKLISTS_PATH = ROOT / "config" / "evidence_checklists.json"
DEFAULT_TESSDATA_DIR = ROOT / "models" / "ocr" / "tessdata"

# The IPC/BNS catalogue is deliberately empty. data/processed/mappings holds
# `pending_human_review` candidates only, and an unreviewed candidate must never
# be served to a user as a mapping. Until a human-approved record exists, every
# lookup must resolve to `not_found`.
CURATED_MAPPINGS: tuple = ()
NO_REVIEWED_MAPPING_WARNING = (
    "This build contains no human-approved IPC/BNS mapping. Extracted candidates exist "
    "but are pending human review and are deliberately not served as mappings. Do not "
    "infer an IPC/BNS equivalence from section numbers; consult the official codes or a "
    "lawyer."
)


class StateError(RuntimeError):
    """A bounded failure while serving a locally cached resource."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass
class ApiState:
    """Startup-loaded, read-mostly application state. No user data is stored."""

    settings: Settings
    corpus_dir: Path
    contacts_path: Path
    checklists_path: Path
    tessdata_dir: Path
    tesseract_path: Path
    ollama_probe_timeout: float = 1.0

    documents: tuple[RetrievalDocument, ...] = ()
    corpus_sha256: str | None = None
    corpus_error: str | None = None

    _scoped: dict[LegalDomain, tuple[RetrievalDocument, ...]] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _finder: LegalAidFinder | None = None
    _checklists: ChecklistCatalog | None = None
    _mappings: MappingCatalog = field(default_factory=lambda: MappingCatalog(CURATED_MAPPINGS))

    # ---- corpus -----------------------------------------------------------------

    def load_corpus(self) -> None:
        """Load the reviewed corpus once. A missing corpus degrades, never crashes."""

        try:
            documents = load_processed_corpus(self.corpus_dir)
        except CorpusLoadError as exc:
            self.documents = ()
            self.corpus_sha256 = None
            self.corpus_error = str(exc)
            return
        self.documents = documents
        self.corpus_sha256 = corpus_sha256(documents)
        self.corpus_error = None

    @property
    def corpus_loaded(self) -> bool:
        return bool(self.documents)

    @property
    def chunk_count(self) -> int:
        return len(self.documents)

    def documents_for_domain(self, domain: LegalDomain) -> tuple[RetrievalDocument, ...]:
        """Return the cached per-domain collection the reviewed router permits."""

        if not self.corpus_loaded:
            raise StateError(
                "corpus_unavailable",
                self.corpus_error or "the processed corpus is not loaded on this device",
            )
        with self._lock:
            cached = self._scoped.get(domain)
            if cached is not None:
                return cached
            try:
                scoped = collection_for_domain(self.documents, domain)
            except CollectionError as exc:
                raise StateError("domain_not_routed", str(exc)) from exc
            self._scoped[domain] = scoped
            return scoped

    # ---- reviewed local resources -----------------------------------------------

    def legal_aid_finder(self) -> LegalAidFinder:
        with self._lock:
            if self._finder is None:
                try:
                    self._finder = LegalAidFinder(self.contacts_path)
                except LegalAidFinderError:
                    raise
                except OSError as exc:
                    raise StateError(
                        "directory_unreadable", "could not read the local legal-aid directory"
                    ) from exc
            return self._finder

    def checklist_catalog(self) -> ChecklistCatalog:
        with self._lock:
            if self._checklists is None:
                try:
                    self._checklists = ChecklistCatalog(self.checklists_path)
                except ChecklistError:
                    raise
                except OSError as exc:
                    raise StateError(
                        "checklists_unavailable", "could not read the local checklist catalogue"
                    ) from exc
            return self._checklists

    @property
    def mapping_catalog(self) -> MappingCatalog:
        return self._mappings

    def ocr_config(self) -> OCRConfig:
        return OCRConfig(
            tessdata_dir=self.tessdata_dir,
            language=OCRLanguage.ENGLISH_HINDI,
            tesseract_path=self.tesseract_path,
        )

    # ---- best-effort local runtime probe ------------------------------------------

    def ollama_reachable(self) -> bool:
        """Probe the loopback runtime. This must never raise and never leaves the device."""

        try:
            from src.agents.ollama import OllamaClient

            OllamaClient(self.settings.ollama_url, timeout=self.ollama_probe_timeout).version()
        except Exception:  # noqa: BLE001 - a health probe must not fail the request
            return False
        return True


def build_state() -> ApiState:
    """Assemble state from the project's existing environment configuration."""

    settings = Settings.from_env()
    corpus_dir = Path(settings.corpus_path)
    if not corpus_dir.is_absolute():
        corpus_dir = ROOT / corpus_dir
    return ApiState(
        settings=settings,
        corpus_dir=corpus_dir,
        contacts_path=Path(os.getenv("NYAYA_CONTACTS_PATH", str(DEFAULT_CONTACTS_PATH))),
        checklists_path=Path(os.getenv("NYAYA_CHECKLISTS_PATH", str(DEFAULT_CHECKLISTS_PATH))),
        tessdata_dir=Path(os.getenv("NYAYA_TESSDATA_DIR", str(DEFAULT_TESSDATA_DIR))),
        tesseract_path=Path(os.getenv("NYAYA_TESSERACT_PATH", str(DEFAULT_TESSERACT_PATH))),
    )
