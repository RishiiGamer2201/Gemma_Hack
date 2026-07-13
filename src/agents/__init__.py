"""Adapters and grounded workflows for optional, strictly local model runtimes."""

from .devils_advocate import (
    AdvocateEvent,
    AdvocateStage,
    DevilsAdvocateError,
    EventKind,
    run_devils_advocate_stream,
)
from .drafter import DraftError, draft_answer, uncited_section_references
from .ollama import OllamaClient, OllamaError, OllamaResponse, OllamaStreamChunk
from .researcher import EvidenceBundle, ResearchError, build_query, retrieve_evidence
from .verifier import VerificationError, unsupported_claims, verify_answer

__all__ = [
    "AdvocateEvent",
    "AdvocateStage",
    "DevilsAdvocateError",
    "DraftError",
    "EventKind",
    "EvidenceBundle",
    "OllamaClient",
    "OllamaError",
    "OllamaResponse",
    "OllamaStreamChunk",
    "ResearchError",
    "VerificationError",
    "build_query",
    "draft_answer",
    "retrieve_evidence",
    "run_devils_advocate_stream",
    "uncited_section_references",
    "unsupported_claims",
    "verify_answer",
]
