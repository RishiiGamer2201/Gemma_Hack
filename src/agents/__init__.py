"""Adapters for optional, strictly local model runtimes."""

from .ollama import OllamaClient, OllamaError, OllamaResponse

__all__ = ["OllamaClient", "OllamaError", "OllamaResponse"]
