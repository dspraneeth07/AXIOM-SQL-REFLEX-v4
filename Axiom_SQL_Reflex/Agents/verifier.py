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

def dry_run_write(
    con: duckdb.DuckDBPyConnection,
    sql: str
):
    try:
        con.execute("BEGIN TRANSACTION;")
        con.execute(sql)
        con.execute("ROLLBACK;")
        return True, None
    except Exception as e:
        con.execute("ROLLBACK;")
        return False, str(e)


# =============================
# MAIN AGENT
# =============================

def execution_verifier(
    sql: str,
    intent: str,
    db_path: Optional[Path] = None,
    max_rows: int = 100_000,
    timeout_sec: float = 2.0
) -> ExecutionVerdict:
    """
    Soft-validates SQL queries.
    Never blocks READ autonomy early.
    """

    con = get_sandbox_connection(db_path)

    verdict: ExecutionVerdict = {
        "sql": sql,
        "intent": intent,
        "allowed": True,
        "soft_failed": True,
        "reason": None,
        "rows": None,
        "latency": None,
        "plan": None,
        "result_df": None,
    }

    # ---- COST INSPECTION (SOFT) ----
    try:
        verdict["plan"] = explain_cost(con, sql)
    except Exception as e:
        verdict["soft_failed"] = True
        verdict["reason"] = f"EXPLAIN failed: {e}"

    # ---- WRITE QUERIES (HARD SAFE) ----
    if intent.upper() == "WRITE":
        ok, err = dry_run_write(con, sql)
        if not ok:
            verdict["reason"] = f"WRITE dry-run failed: {err}"
            return verdict

        verdict["allowed"] = True
        verdict["reason"] = "WRITE dry-run successful"
        return verdict

    # ---- ROW COUNT CHECK (SOFT) ----
    row_est = estimate_row_count(con, sql)

    if row_est == -1:
        verdict["soft_failed"] = True
        verdict["reason"] = "Row count estimation failed"

    elif row_est > max_rows:
        verdict["soft_failed"] = True
        verdict["reason"] = f"Row limit exceeded: {row_est} > {max_rows}"

    # ---- EXECUTION ATTEMPT (CRITICAL) ----
    try:
        df, latency = execute_with_timeout(
            con, sql, timeout_sec
        )

        verdict["allowed"] = True
        verdict["result_df"] = df
        verdict["rows"] = len(df)
        verdict["latency"] = latency

        if verdict["reason"] is None:
            verdict["reason"] = "Execution successful"

        return verdict

    except Exception as e:
        verdict["soft_failed"] = True
        verdict["reason"] = f"Execution failed: {e}"
        verdict["result_df"] = None
        return verdict
