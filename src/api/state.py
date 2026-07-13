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
from src.agents.ollama import OllamaClient
from src.audio.integrity import PINNED_MODEL_REVISION as ASR_PINNED_REVISION
from src.config import Settings
from src.legal_aid.finder import LegalAidFinder, LegalAidFinderError
from src.legal_time.mapping import MappingCatalog
from src.models.schemas import LegalDomain
from src.ocr import DEFAULT_TESSERACT_PATH, OCRConfig, OCRLanguage
from src.retrieval import CorpusLoadError, RetrievalDocument, corpus_sha256, load_processed_corpus
from src.retrieval.collections import CollectionError, collection_for_domain
from src.retrieval.embeddings import DEFAULT_EMBEDDING_MODEL, EmbeddingError, LocalEmbedder

ROOT = Path(__file__).resolve().parents[2]

DEFAULT_CORPUS_DIR = ROOT / "data" / "processed" / "sections"
DEFAULT_CONTACTS_PATH = ROOT / "data" / "processed" / "contacts" / "delhi_dlsa.json"
DEFAULT_CHECKLISTS_PATH = ROOT / "config" / "evidence_checklists.json"
DEFAULT_TESSDATA_DIR = ROOT / "models" / "ocr" / "tessdata"
DEFAULT_ASR_MODEL_DIR = ROOT / "models" / "asr" / "faster-whisper-small"

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
    # Drafting and verification are several sequential local generations.
    generation_timeout: float = 300.0

    documents: tuple[RetrievalDocument, ...] = ()
    corpus_sha256: str | None = None
    corpus_error: str | None = None

    # Semantic retrieval and generation both need the local runtime. Both degrade
    # rather than crash when it is absent: retrieval falls back to lexical only,
    # and answer generation is refused with a clear error.
    embedding_model: str = DEFAULT_EMBEDDING_MODEL
    index_dir: Path = Path("data/indexes")
    asr_model_dir: Path = Path("models/asr/faster-whisper-small")
    asr_model_revision: str = ASR_PINNED_REVISION
    # Off by default so constructing state never reaches the local runtime. The
    # real server turns it on in build_state(); tests stay hermetic and fast.
    use_embeddings: bool = False

    _scoped: dict[LegalDomain, tuple[RetrievalDocument, ...]] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _finder: LegalAidFinder | None = None
    _checklists: ChecklistCatalog | None = None
    _embedder: LocalEmbedder | None = None
    _client: OllamaClient | None = None
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

    # ---- local model runtime ----------------------------------------------------

    def model_client(self) -> OllamaClient:
        """Return the loopback-only client. Constructing it performs no I/O."""

        with self._lock:
            if self._client is None:
                self._client = OllamaClient(
                    self.settings.ollama_url, timeout=self.generation_timeout
                )
            return self._client

    def embedding_callback(self):
        """Return a cached local embedder, or None when the runtime is unavailable.

        A missing embedding runtime must degrade retrieval to lexical-only rather
        than fail the request: a lexical answer with real citations is still safe,
        whereas no answer at all helps nobody.
        """

        if not self.use_embeddings:
            return None
        with self._lock:
            if self._embedder is None:
                try:
                    self._embedder = LocalEmbedder(
                        self.model_client(),
                        model=self.embedding_model,
                        cache_dir=self.index_dir,
                    )
                except EmbeddingError:
                    self.use_embeddings = False
                    return None
            return self._embedder

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
    index_dir = Path(settings.index_path)
    if not index_dir.is_absolute():
        index_dir = ROOT / index_dir
    return ApiState(
        settings=settings,
        corpus_dir=corpus_dir,
        contacts_path=Path(os.getenv("NYAYA_CONTACTS_PATH", str(DEFAULT_CONTACTS_PATH))),
        checklists_path=Path(os.getenv("NYAYA_CHECKLISTS_PATH", str(DEFAULT_CHECKLISTS_PATH))),
        tessdata_dir=Path(os.getenv("NYAYA_TESSDATA_DIR", str(DEFAULT_TESSDATA_DIR))),
        asr_model_dir=Path(os.getenv("NYAYA_ASR_MODEL_DIR", str(DEFAULT_ASR_MODEL_DIR))),
        tesseract_path=Path(os.getenv("NYAYA_TESSERACT_PATH", str(DEFAULT_TESSERACT_PATH))),
        index_dir=index_dir,
        # The served application uses the semantic channel; it degrades to
        # lexical-only if the local embedding runtime is unavailable.
        use_embeddings=os.getenv("NYAYA_USE_EMBEDDINGS", "1") != "0",
    )
