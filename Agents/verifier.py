"""
Execution Verifier Agent

Safely validates SQL queries via:
- Cost inspection (soft)
- Row count estimation (soft)
- Timeout-bounded execution
- Write-query dry runs (hard)

Enterprise-grade design:
❌ Never blocks autonomy early
✅ Reports uncertainty instead
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Optional, TypedDict

import duckdb


# =============================
# Types
# =============================

class ExecutionVerdict(TypedDict):
    sql: str
    intent: str
    allowed: bool
    soft_failed: bool
    reason: Optional[str]
    rows: Optional[int]
    latency: Optional[float]
    plan: Optional[str]
    result_df: Optional[object]


# =============================
# Connection Management
# =============================

def get_sandbox_connection(
    spider_db_path: Optional[Path] = None
) -> duckdb.DuckDBPyConnection:
    """
    Creates an in-memory DuckDB sandbox.
    Optionally attaches a SQLite database.
    """
    con = duckdb.connect(database=":memory:")

    if spider_db_path is None:
        return con

    db_path = spider_db_path.resolve()
    if not db_path.exists():
        raise FileNotFoundError(db_path)

    # Enable SQLite
    con.execute("INSTALL sqlite;")
    con.execute("LOAD sqlite;")

    con.execute(
        f"ATTACH DATABASE '{db_path}' AS spider_db (TYPE sqlite);"
    )

    con.execute("SET schema 'spider_db';")
    return con
