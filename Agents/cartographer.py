"""
GraphRAG Cartographer Agent

Schema-grounded table discovery, join-path inference,
and ambiguity detection for Text-to-SQL systems.
"""

from typing import Dict, List, Set, Tuple, Protocol
from collections import Counter, defaultdict
from pathlib import Path
import math
import sqlite3

import networkx as nx
import numpy as np
import faiss

from agents.embeddings import HFTextEmbedder

# ============================================================
# TOKENIZATION (SINGLE SOURCE OF TRUTH)
# ============================================================

def tokenize(text: str) -> List[str]:
    return text.lower().split()

# ============================================================
# PHASE 1 — SCHEMA GRAPH BUILDER (PER DB)
# ============================================================

def build_schema_graph(
    db_path: Path
) -> Tuple[nx.Graph, List[str], List[str], List[List[str]]]:

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    graph = nx.Graph()
    schema_texts = []
    schema_ids = []
    doc_tokens = []

    # ---- Tables ----
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [t[0] for t in cur.fetchall()]

    for table in tables:
        graph.add_node(table, type="table")

        cur.execute(f"PRAGMA table_info({table})")
        cols = [c[1] for c in cur.fetchall()]

        text = f"table {table} with columns " + " ".join(cols)
        schema_texts.append(text)
        schema_ids.append(table)
        doc_tokens.append(tokenize(text))

    # ---- Foreign Keys ----
    for table in tables:
        cur.execute(f"PRAGMA foreign_key_list({table})")
        for _, _, ref_table, *_ in cur.fetchall():
            if ref_table in tables:
                graph.add_edge(table, ref_table, type="fk")

    conn.close()
    return graph, schema_texts, schema_ids, doc_tokens