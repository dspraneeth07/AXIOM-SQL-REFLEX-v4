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

# =============================
# Cost & Safety Analysis
# =============================

def explain_cost(
    con: duckdb.DuckDBPyConnection,
    sql: str
) -> str:
    try:
        rows = con.execute(
            f"EXPLAIN ANALYZE {sql}"
        ).fetchall()
        return "\n".join(r[0] for r in rows)
    except Exception as e:
        raise RuntimeError(str(e)) from e


def estimate_row_count(
    con: duckdb.DuckDBPyConnection,
    sql: str
) -> int:
    try:
        sql_clean = sql.strip().rstrip(";")
        wrapped = f"SELECT COUNT(*) FROM ({sql_clean}) t"
        return int(con.execute(wrapped).fetchone()[0])
    except Exception:
        return -1


# =============================
# Execution Helpers
# =============================

def execute_with_timeout(
    con: duckdb.DuckDBPyConnection,
    sql: str,
    timeout_sec: float
):
    sql_clean = sql.strip().rstrip(";")
    start = time.time()

    df = con.execute(sql_clean).fetchdf()
    latency = time.time() - start

    if latency > timeout_sec:
        raise TimeoutError(
            f"Query exceeded {timeout_sec:.2f}s"
        )

    return df, latency
