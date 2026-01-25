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
# ============================================================
# BM25 SUPPORT
# ============================================================

def build_df(doc_tokens: List[List[str]]) -> dict:
    df = Counter()
    for tokens in doc_tokens:
        for t in set(tokens):
            df[t] += 1
    return dict(df)


def bm25_score(
    query: str,
    doc_tokens: List[List[str]],
    df: Dict[str, int],
    k1: float = 1.5,
    b: float = 0.75
) -> List[float]:

    N = len(doc_tokens)
    avgdl = sum(len(d) for d in doc_tokens) / max(N, 1)
    q_tokens = tokenize(query)

    scores = []
    for tokens in doc_tokens:
        score = 0.0
        dl = len(tokens)

        for q in q_tokens:
            if q not in tokens:
                continue

            tf = tokens.count(q)
            df_q = df.get(q, 0)
            idf = math.log((N - df_q + 0.5) / (df_q + 0.5) + 1)

            score += idf * (
                (tf * (k1 + 1)) /
                (tf + k1 * (1 - b + b * dl / avgdl))
            )

        scores.append(score)

    return scores

# ============================================================
# FAISS INDEX BUILDER
# ============================================================

def build_faiss_index(schema_texts: List[str]):
    """
    IMPORTANT:
    schema_texts, schema_ids, doc_tokens, and FAISS index
    MUST be built from the same ordered source.
    Do NOT reorder independently.
    """
    embedder = HFTextEmbedder()
    embeddings = embedder.encode(schema_texts)

    dim = embeddings.shape[1]
    index = faiss.IndexFlatIP(dim)
    index.add(embeddings)

    return embedder, index
# ============================================================
# GRAPH HELPERS
# ============================================================

def khop_tables(
    graph: nx.Graph,
    seed_tables: Set[str],
    k: int = 2
) -> Set[str]:

    visited = set(seed_tables)
    frontier = set(seed_tables)

    for _ in range(k):
        next_frontier = set()
        for node in frontier:
            for n in graph.neighbors(node):
                if graph.nodes[n].get("type") == "table" and n not in visited:
                    visited.add(n)
                    next_frontier.add(n)
        frontier = next_frontier

    return visited


def find_join_paths(
    graph: nx.Graph,
    tables: Set[str]
) -> Dict[Tuple[str, str], List[str]]:

    paths = {}
    tables = list(tables)

    for i in range(len(tables)):
        for j in range(i + 1, len(tables)):
            t1, t2 = tables[i], tables[j]
            try:
                paths[(t1, t2)] = nx.shortest_path(graph, t1, t2)
            except nx.NetworkXNoPath:
                continue

    return paths

# ============================================================
# MAIN CARTOGRAPHER AGENT
# ============================================================

class Embedder(Protocol):
    def encode(self, texts: List[str], normalize_embeddings: bool = True) -> np.ndarray: ...


def graphrag_cartographer(
    question: str,
    graph: nx.Graph,
    schema_texts: List[str],
    schema_ids: List[str],
    embedder: Embedder,
    faiss_index: faiss.Index,
    doc_tokens: List[List[str]],
    df: Dict[str, int],
    top_k: int = 8,
    khop: int = 2
) -> Dict:

    # ---- Dense retrieval ----
    q_emb = embedder.encode([question], normalize_embeddings=True)
    _, idxs = faiss_index.search(q_emb, top_k)
    valid_ids = set()
    max_idx = len(schema_ids)

    for i in idxs[0]:
        if i == -1:
            continue
        if 0 <= i < max_idx:
            valid_ids.add(schema_ids[i])

    retrieved = valid_ids


    # ---- Sparse reranking ----
    bm25_scores = bm25_score(question, doc_tokens, df)
    ranked = [
        (schema_ids[i], bm25_scores[i])
        for i in range(len(schema_ids))
        if schema_ids[i] in retrieved
    ]
    ranked.sort(key=lambda x: x[1], reverse=True)

    seed_tables = {sid.split(".")[0] for sid, _ in ranked[:5]}

    # ---- Graph expansion ----
    expanded_tables = khop_tables(graph, seed_tables, k=khop)

    # ---- Join paths ----
    join_paths = find_join_paths(graph, expanded_tables)

    # ---- Ambiguity detection (enterprise-grade) ----
    ambiguous = (
        len(seed_tables) > 1 and
        (len(join_paths) == 0 or len(join_paths) > 5)
    )

    return {
        "question": question,
        "seed_tables": list(seed_tables),
        "expanded_tables": list(expanded_tables),
        "join_paths": join_paths,
        "ambiguous": ambiguous
    }
