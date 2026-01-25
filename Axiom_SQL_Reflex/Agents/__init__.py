"""
Axiom SQL-Reflex v4 — Agents Package

This package exposes the core agent components and a unified entrypoint
for running the full Text-to-SQL reflex pipeline.

Design goals:
- Explicit dependency injection
- Lazy, resource-safe model loading
- No hard-coded paths
- Import-safe (no heavy work at import time)
"""

from pathlib import Path
from typing import Optional, Dict, Any

from llama_cpp import Llama

# ---- Public agent primitives ----
from .cartographer import graphrag_cartographer
from .architect import architect_ensemble
from .verifier import execution_verifier
from .critic import semantic_verifier
from .orchestrator import reflex_orchestrator

__all__ = [
    "AxiomAgent",
    "graphrag_cartographer",
    "architect_ensemble",
    "execution_verifier",
    "semantic_verifier",
    "reflex_orchestrator",
]


class AxiomAgent:
    """
    High-level entrypoint for Axiom SQL-Reflex v4.

    This class is intentionally thin.
    It wires together models, schema context, and the reflex orchestrator.

    Heavy artifacts (LLMs, schema graphs) are loaded lazily.
    """

    def __init__(
        self,
        *,
        model_dir: Path,
        data_dir: Path,
        n_threads: int = 8,
        verbose: bool = False,
    ):
        self.model_dir = Path(model_dir)
        self.data_dir = Path(data_dir)

        self.n_threads = n_threads
        self.verbose = verbose

        # ---- Lazy-loaded resources ----
        self._llm_large: Optional[Llama] = None
        self._llm_medium: Optional[Llama] = None

        # Schema / retrieval artifacts (optional, injected later)
        self._schema_cache: Dict[str, Dict[str, Any]] = {}

    # ======================================================
    # LLM LOADERS (LAZY)
    # ======================================================

    @property
    def llm_large(self) -> Llama:
        if self._llm_large is None:
            path = self.model_dir / "deepseek-coder-6.7b-instruct.Q4_K_M.gguf"
            if not path.exists():
                raise FileNotFoundError(f"Large model not found: {path}")

            self._llm_large = Llama(
                model_path=str(path),
                n_ctx=2048,
                n_threads=self.n_threads,
                n_batch=256,
                verbose=self.verbose,
            )
        return self._llm_large

    @property
    def llm_medium(self) -> Llama:
        if self._llm_medium is None:
            path = self.model_dir / "mistral-7b-instruct-v0.2.Q4_K_M.gguf"
            if not path.exists():
                raise FileNotFoundError(f"Medium model not found: {path}")

            self._llm_medium = Llama(
                model_path=str(path),
                n_ctx=2048,
                n_threads=self.n_threads,
                n_batch=256,
                verbose=self.verbose,
            )
        return self._llm_medium

    # ======================================================
    # PUBLIC API
    # ======================================================

    def run(
        self,
        *,
        question: str,
        db_id: str,
        schema_context: Dict[str, Any],
        max_retries: int = 5,
        min_confidence: float = 0.6,
    ) -> Dict[str, Any]:
        """
        Execute the full reflex pipeline for a single question.

        Parameters
        ----------
        question : str
            Natural language question.
        db_id : str
            Spider/BIRD database id.
        schema_context : dict
            Pre-built schema artifacts:
            {
                graph,
                schema_texts,
                schema_ids,
                embedder,
                faiss_index,
                doc_tokens,
                df_stats
            }
        """

        db_path = self.data_dir / "spider" / "database" / db_id / f"{db_id}.sqlite"
        if not db_path.exists():
            raise FileNotFoundError(f"Database not found: {db_path}")

        return reflex_orchestrator(
            question=question,
            db_path=db_path,
            graph=schema_context["graph"],
            schema_texts=schema_context["schema_texts"],
            schema_ids=schema_context["schema_ids"],
            embedder=schema_context["embedder"],
            faiss_index=schema_context["faiss_index"],
            doc_tokens=schema_context["doc_tokens"],
            df_stats=schema_context["df_stats"],
            llm_large=self.llm_large,
            llm_medium=self.llm_medium,
            max_retries=max_retries,
            min_confidence=min_confidence,
        )
