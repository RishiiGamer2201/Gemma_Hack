"""Loopback-only HTTP surface over the existing offline legal modules.

The API layer adds no legal logic of its own. It validates requests, calls the
reviewed deterministic modules, and returns exactly what they return, including
every warning they emit.
"""

from .app import create_app
from .state import ApiState, StateError, build_state

__all__ = ["ApiState", "StateError", "build_state", "create_app"]
