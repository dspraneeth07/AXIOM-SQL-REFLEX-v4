"""
API data contracts for Axiom SQL-Reflex.

These models define the public, stable interface between clients
and the agentic Text-to-SQL runtime. They are intentionally strict,
explicit, and forward-compatible.
"""

from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, validator


# -------------------------
# Enumerations
# -------------------------

class QueryMode(str, Enum):
    """
    Execution mode for a query request.
    """
    READ = "read"
    WRITE = "write"
    AUTO = "auto"


class QueryStatus(str, Enum):
    """
    Terminal status of a query execution.
    """
    SUCCESS = "success"
    FAILED = "failed"
    REJECTED = "rejected"


# -------------------------
# Request Models
# -------------------------

class QueryRequest(BaseModel):
    """
    Input contract for submitting a natural language query.

    This model intentionally avoids exposing internal agent details.
    """

    question: str = Field(
        ...,
        description="Natural language question to be converted into SQL.",
        min_length=3,
        max_length=1_000,
        examples=["How many singers are there?"],
    )

    db_id: str = Field(
        ...,
        description="Target database identifier (Spider/BIRD DB name).",
        examples=["concert_singer"],
    )

    mode: QueryMode = Field(
        QueryMode.AUTO,
        description="Execution mode hint (read/write/auto).",
    )

    max_retries: int = Field(
        5,
        ge=1,
        le=10,
        description="Maximum number of agent retries before termination.",
    )

    min_confidence: float = Field(
        0.6,
        ge=0.0,
        le=1.0,
        description="Minimum semantic confidence required to accept a result.",
    )

    @validator("question")
    def normalize_question(cls, v: str) -> str:
        return v.strip()


# -------------------------
# Response Models
# -------------------------

class ExecutionStats(BaseModel):
    """
    Low-level execution statistics returned for observability.
    """

    latency_sec: Optional[float] = Field(
        None,
        description="Wall-clock execution latency in seconds.",
    )

    rows_returned: Optional[int] = Field(
        None,
        description="Number of rows produced by the query.",
    )


class QueryResponse(BaseModel):
    """
    Output contract for a query request.

    Every response is explicit about success or failure.
    Silent failures are not allowed.
    """

    status: QueryStatus = Field(
        ...,
        description="Final execution status.",
    )

    sql: Optional[str] = Field(
        None,
        description="Final SQL statement selected by the agent.",
    )

    confidence: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Semantic confidence score assigned by the critic.",
    )

    stats: Optional[ExecutionStats] = Field(
        None,
        description="Execution statistics, if available.",
    )

    reason: Optional[str] = Field(
        None,
        description="Human-readable explanation for failure or rejection.",
    )

    metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Optional structured metadata for debugging or analysis.",
    )


# -------------------------
# Health / System Models
# -------------------------

class HealthResponse(BaseModel):
    """
    Health check response for service monitoring.
    """

    status: str = Field("ok", description="Service health status.")
