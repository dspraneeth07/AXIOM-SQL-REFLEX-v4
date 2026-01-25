"""
Axiom SQL-Reflex

An execution-aware, multi-agent Text-to-SQL system designed for
research and applied experimentation on real database schemas.

This package exposes a minimal public API. Internal agent logic,
retrieval pipelines, and execution safeguards are intentionally
kept modular and explicit.
"""

from .agents import AxiomAgent

__all__ = [
    "AxiomAgent",
]

__version__ = "0.1.0"
