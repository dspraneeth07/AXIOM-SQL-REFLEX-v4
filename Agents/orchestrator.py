"""
Reflex Orchestrator Agent

Central brain of AXIOM SQL-REFLEX v4.

Responsibilities:
- Agent routing
- Retry budgeting
- Convergence detection
- Partial-success handling
- Enterprise-grade autonomy
"""

from typing import Dict, Any, List
from pathlib import Path
import hashlib

from agents.cartographer import graphrag_cartographer
from agents.architect import architect_ensemble
from agents.verifier import execution_verifier
from agents.critic import semantic_verifier


def reflex_orchestrator(
    *,
    question: str,
    schema_text: str,
    db_path: Path,

    graph,
    schema_texts,
    schema_ids,
    embedder,
    faiss_index,
    doc_tokens,
    df_stats,

    llm_large,
    llm_medium,
    critic_llm_param,

    max_retries: int = 5,
    min_confidence: float = 0.6
) -> Dict[str, Any]:
    """
    Enterprise-grade reflex loop.
    Never aborts early.
    Never lies.
    """

    sql_fingerprints: List[str] = []

    def fingerprint(sql: str) -> str:
        return hashlib.sha256(
            sql.lower().strip().encode()
        ).hexdigest()

    retries = 0
    schema_context = None

    while retries < max_retries:
        retries += 1

        # =====================================================
        # 1️⃣ CARTOGRAPHER
        # =====================================================
        if schema_context is None:
            schema_context = graphrag_cartographer(
                question=question,
                graph=graph,
                schema_texts=schema_texts,
                schema_ids=schema_ids,
                embedder=embedder,
                faiss_index=faiss_index,
                doc_tokens=doc_tokens,
                df=df_stats
            )

        # =====================================================
        # 2️⃣ ARCHITECT (FOCUSED SCHEMA)
        # =====================================================
        focused_tables = schema_context["expanded_tables"]

        focused_schema_text = "\n".join(
            f"- {t}" for t in focused_tables
        )

        candidates = architect_ensemble(
            question=question,
            schema=focused_schema_text,
            llm_large=llm_large,
            llm_medium=llm_medium
        )

        if not candidates:
            return {
                "status": "failed",
                "reason": "No SQL generated",
                "iterations": retries
            }

        # =====================================================
        # 3️⃣ TRY EACH CANDIDATE
        # =====================================================
        for cand in candidates:
            sql = cand["sql"]
            intent = cand["intent"]

            fp = fingerprint(sql)
            sql_fingerprints.append(fp)

            # ---- REAL convergence detection ----
            if (
                len(sql_fingerprints) >= 3 and
                sql_fingerprints[-1] ==
                sql_fingerprints[-2] ==
                sql_fingerprints[-3]
            ):
                return {
                    "status": "failed",
                    "reason": "Convergence detected",
                    "iterations": retries
                }

            # =================================================
            # 4️⃣ EXECUTION VERIFIER (SOFT)
            # =================================================
            exec_v = execution_verifier(
                sql=sql,
                intent=intent,
                db_path=db_path
            )

            # =================================================
            # 5️⃣ SEMANTIC CRITIC — ALWAYS RUN
            # =================================================
            sem_v = semantic_verifier(
                question=question,
                sql=sql,
                df=exec_v.get("result_df"),
                llm=critic_llm_param,
                min_confidence=min_confidence
            )

            # =================================================
            # 6️⃣ ACCEPTANCE LOGIC
            # =================================================
            if sem_v["ok"]:
                return {
                    "status": "success",
                    "sql": sql,
                    "confidence": sem_v["confidence"],
                    "rows": exec_v.get("rows"),
                    "latency": exec_v.get("latency"),
                    "iterations": retries
                }

            # ❌ Not good enough → try next SQL
            continue

        # =====================================================
        # 7️⃣ RESET CONTEXT & RETRY
        # =====================================================
        schema_context = None

    # =========================================================
    # ❌ RETRY BUDGET EXHAUSTED
    # =========================================================
    return {
        "status": "failed",
        "reason": "Retry budget exhausted",
        "iterations": retries
    }
