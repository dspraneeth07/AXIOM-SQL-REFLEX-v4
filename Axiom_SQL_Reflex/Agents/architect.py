"""
Architect Agent

Generates multiple SQL hypotheses using an ensemble of LLMs,
and annotates intent + expected output shape.
"""

from typing import List, Dict, TypedDict
import re


# -----------------------------
# Types
# -----------------------------

class ArchitectCandidate(TypedDict):
    sql: str
    intent: str
    expected_shape: str


# -----------------------------
# Prompt
# -----------------------------

SQL_PROMPT = """
You are an expert SQL engineer.

STRICT RULES:
- Use ONLY the provided schema
- Do NOT invent tables or columns
- Output ONLY ONE SQL query
- No explanations, no markdown
- Must start with SELECT

Schema:
{schema}

Question:
{question}

SQL:
SELECT
"""


# -----------------------------
# Core Helpers
# -----------------------------

def generate_sql(llm, schema: str, question: str) -> str | None:
    prompt = SQL_PROMPT.format(schema=schema, question=question)

    out = llm(
        prompt,
        max_tokens=256,
        stop=[";", "\n\n"]
    )

    text = out["choices"][0]["text"].strip()
    if not text:
        return None

    sql = "SELECT " + text
    sql = re.sub(r"\s+", " ", sql).strip()

    if not sql.lower().startswith("select"):
        return None

    return sql + ";"


def classify_intent(sql: str) -> str:
    sql_l = sql.lower()
    if any(k in sql_l for k in ["insert", "update", "delete", "create", "drop", "alter"]):
        return "WRITE"
    return "READ"


def infer_output_shape(sql: str) -> str:
    sql_l = sql.lower()

    if any(k in sql_l for k in ["count(", "max(", "min(", "avg(", "sum("]):
        return "single-row"

    if "group by" in sql_l:
        return "multi-row"

    return "multi-row"


def validate_sql(sql: str, schema: str) -> bool:
    schema_tables = set(re.findall(r"-\s*(\w+)\(", schema))
    used_tables = set(re.findall(r"from\s+(\w+)|join\s+(\w+)", sql.lower()))
    used_tables = {t for pair in used_tables for t in pair if t}
    return used_tables.issubset(schema_tables)


# -----------------------------
# MAIN AGENT
# -----------------------------

def architect_ensemble(
    question: str,
    schema: str,
    llm_large,
    llm_medium,
    max_candidates: int = 5
):
    raw_sqls = []

    if llm_large is not None:
        sql = generate_sql(llm_large, schema, question)
        if sql:
            raw_sqls.append(sql)

    if llm_medium is not None:
        for _ in range(2):
            sql = generate_sql(llm_medium, schema, question)
            if sql:
                raw_sqls.append(sql)



    raw_sqls = list(dict.fromkeys(raw_sqls))[:max_candidates]

    results: List[ArchitectCandidate] = []
    # ---- Validate but DO NOT DROP ----
    for sql in raw_sqls:
        candidate = {
            "sql": sql,
            "intent": classify_intent(sql),
            "expected_shape": infer_output_shape(sql),
        }

        if not validate_sql(sql, schema):
            candidate["weak"] = True

        results.append(candidate)

    # ---- HARD FALLBACK (NON-NEGOTIABLE) ----
    if not results and raw_sqls:
        results.append({
            "sql": raw_sqls[0],
            "intent": classify_intent(raw_sqls[0]),
            "expected_shape": infer_output_shape(raw_sqls[0]),
            "weak": True
        })

    return results

