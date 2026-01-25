"""
Semantic Critic Agent (Enterprise-Grade)

Evaluates whether SQL semantically answers a question,
even under partial or failed execution.
"""

from __future__ import annotations

import json
from typing import TypedDict
import pandas as pd


# =============================
# Types
# =============================

class SemanticVerdict(TypedDict):
    ok: bool
    confidence: float
    reason: str


# =============================
# Heuristic Guards
# =============================

def metric_sanity_check(question: str, sql: str) -> bool:
    q = question.lower()
    s = sql.lower()

    rules = [
        (["count", "number of"], "count("),
        (["average", "avg", "mean"], "avg("),
        (["maximum", "highest", "max"], "max("),
        (["minimum", "lowest", "min"], "min("),
    ]

    for keywords, token in rules:
        if any(k in q for k in keywords) and token not in s:
            return False

    return True


# =============================
# Result Summarization
# =============================

def summarize_result(df, max_rows: int = 5) -> str:
    """
    Produces a compact summary.
    IMPORTANT: df may be None.
    """

    if df is None:
        return "NO RESULT (execution failed or skipped)"

    if not isinstance(df, pd.DataFrame):
        return f"INVALID RESULT TYPE: {type(df).__name__}"

    if df.empty:
        return "EMPTY RESULT"

    summary = {
        "columns": list(df.columns),
        "row_count": int(len(df)),
        "sample_rows": df.head(max_rows).to_dict(orient="records"),
    }

    return json.dumps(summary, indent=2)


# =============================
# LLM Critic
# =============================

def run_llm_critic(
    llm,
    question: str,
    sql: str,
    result_summary: str,
    min_confidence: float
) -> SemanticVerdict:

    prompt = f"""
You are a senior data auditor.

Judge whether the SQL logically answers the question.
Execution may have failed — judge intent and logic.

Return ONLY JSON:
{{
  "verdict": "correct" | "incorrect",
  "confidence": number between 0 and 1,
  "reason": "short explanation"
}}

Question:
{question}

SQL:
{sql}

Result Preview:
{result_summary}
"""

    out = llm(prompt, max_tokens=256)
    text = out["choices"][0]["text"].strip()

    try:
        start = text.find("{")
        end = text.rfind("}") + 1
        verdict = json.loads(text[start:end])
    except Exception:
        return {
            "ok": False,
            "confidence": 0.0,
            "reason": "Invalid JSON from critic",
        }

    confidence = float(verdict.get("confidence", 0.0))
    ok = verdict.get("verdict") == "correct" and confidence >= min_confidence

    return {
        "ok": ok,
        "confidence": confidence,
        "reason": verdict.get("reason", ""),
    }


# =============================
# MAIN AGENT
# =============================

def semantic_verifier(
    question: str,
    sql: str,
    df,
    llm,
    min_confidence: float = 0.6
) -> SemanticVerdict:
    """
    Enterprise semantic verifier.
    NEVER hard-fails on execution issues.
    """

    # ---- Fast heuristic ----
    if not metric_sanity_check(question, sql):
        return {
            "ok": False,
            "confidence": 0.0,
            "reason": "Metric mismatch detected",
        }

    result_summary = summarize_result(df)

    return run_llm_critic(
        llm=llm,
        question=question,
        sql=sql,
        result_summary=result_summary,
        min_confidence=min_confidence
    )
