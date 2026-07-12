"""Official-source corpus acquisition and deterministic processing."""

from .chunker import SectionChunk, chunk_sections, write_jsonl
from .extract import ExtractionError, ExtractedDocument, ExtractedPage, extract_document
from .manifest import OfficialSource, SourceManifest, load_manifest
from .pipeline import (
    CorpusBuildError,
    CorpusBuildReport,
    SourceBuildFailure,
    SourceBuildResult,
    build_corpus,
)

__all__ = [
    "ExtractedDocument",
    "ExtractedPage",
    "ExtractionError",
    "CorpusBuildError",
    "CorpusBuildReport",
    "OfficialSource",
    "SectionChunk",
    "SourceManifest",
    "SourceBuildFailure",
    "SourceBuildResult",
    "build_corpus",
    "chunk_sections",
    "extract_document",
    "load_manifest",
    "write_jsonl",
]
