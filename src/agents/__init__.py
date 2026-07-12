"""Adapters and grounded workflows for optional, strictly local model runtimes."""

from .devils_advocate import (
    AdvocateEvent,
    AdvocateStage,
    DevilsAdvocateError,
    EventKind,
    run_devils_advocate_stream,
)
from .ollama import OllamaClient, OllamaError, OllamaResponse, OllamaStreamChunk

__all__ = [
    "AdvocateEvent",
    "AdvocateStage",
    "DevilsAdvocateError",
    "EventKind",
    "OllamaClient",
    "OllamaError",
    "OllamaResponse",
    "OllamaStreamChunk",
    "run_devils_advocate_stream",
]
