from pathlib import Path
from threading import Lock
import os

from axiom_sql_reflex.agents import AxiomAgent

# Singleton state
_AGENT: AxiomAgent | None = None
_LOCK = Lock()


def get_agent() -> AxiomAgent:
    """
    Returns a singleton AxiomAgent instance.

    - Thread-safe
    - Lazy-loaded
    - Environment-configurable
    """

    global _AGENT

    if _AGENT is None:
        with _LOCK:
            if _AGENT is None:  # double-checked locking
                model_dir = Path(
                    os.getenv("AXIOM_MODEL_DIR", "/app/models")
                )
                db_dir = Path(
                    os.getenv("AXIOM_DB_DIR", "/app/data/spider/database")
                )

                _AGENT = AxiomAgent(
                    model_dir=model_dir,
                    db_dir=db_dir,
                )

    return _AGENT
