"""
Axiom SQL-Reflex v4 – Local FastAPI Runtime

This service exposes a minimal, execution-aware Text-to-SQL agent
as a local HTTP API. It is intentionally simple, synchronous, and
CPU-friendly to match research and evaluation workloads.

No external APIs. No hidden state.
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from pathlib import Path
import time
import logging

from axiom_sql_reflex.api.models import QueryRequest, QueryResponse
from axiom_sql_reflex.agents import AxiomAgent

# ---------------------------------------------------------
# Logging (explicit, quiet by default)
# ---------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("axiom-sql-reflex")

# ---------------------------------------------------------
# Global runtime (loaded once)
# ---------------------------------------------------------
AGENT: AxiomAgent | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifecycle hook.

    Loads models once at startup and keeps them resident
    for the lifetime of the process.
    """
    global AGENT

    logger.info("Initializing Axiom SQL-Reflex runtime")

    AGENT = AxiomAgent(
        model_dir=Path("/app/models"),
        db_dir=Path("/app/data/spider/database"),
    )

    logger.info("Runtime initialized successfully")
    yield
    logger.info("Shutting down Axiom SQL-Reflex runtime")


# ---------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------
app = FastAPI(
    title="Axiom SQL-Reflex v4",
    version="0.1.0",
    description=(
        "Execution-aware, multi-agent Text-to-SQL system "
        "with semantic validation. Runs fully locally."
    ),
    lifespan=lifespan,
)


# ---------------------------------------------------------
# Health check
# ---------------------------------------------------------
@app.get("/health", tags=["system"])
def health() -> dict:
    """
    Lightweight health endpoint.
    Does not trigger model loading or execution.
    """
    return {"status": "ok"}


# ---------------------------------------------------------
# Main inference endpoint
# ---------------------------------------------------------
@app.post("/query", response_model=QueryResponse, tags=["inference"])
def query(req: QueryRequest) -> QueryResponse:
    """
    Convert a natural language question into SQL and execute it safely.

    This endpoint:
    - Grounds schema via GraphRAG
    - Generates multiple SQL candidates
    - Executes with cost & timeout guards
    - Validates semantics with an LLM critic
    - Retries selectively until convergence or budget exhaustion
    """

    if AGENT is None:
        raise HTTPException(status_code=503, detail="Agent not initialized")

    start_time = time.time()

    try:
        result = AGENT.run(
            question=req.question,
            db_id=req.db_id,
        )
    except Exception as e:
        logger.exception("Unhandled runtime error")
        raise HTTPException(status_code=500, detail=str(e))

    latency = time.time() - start_time

    # -----------------------------
    # Failure path
    # -----------------------------
    if result.get("status") != "success":
        return QueryResponse(
            status="failed",
            reason=result.get("reason", "unknown failure"),
            latency=latency,
        )

    # -----------------------------
    # Success path
    # -----------------------------
    return QueryResponse(
        status="success",
        sql=result.get("sql"),
        confidence=result.get("confidence"),
        rows=result.get("rows"),
        latency=latency,
    )


# ---------------------------------------------------------
# Optional: root endpoint
# ---------------------------------------------------------
@app.get("/", include_in_schema=False)
def root():
    return JSONResponse(
        {
            "service": "Axiom SQL-Reflex v4",
            "status": "running",
            "docs": "/docs",
        }
    )
