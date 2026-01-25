import pickle
from pathlib import Path
import networkx as nx
import duckdb

from agents.embeddings import HFTextEmbedder
from agents.cartographer import tokenize
from collections import Counter

def build_schema_graph_for_db(db_id, sqlite_path, output_dir):
    con = duckdb.connect()
    con.execute("INSTALL sqlite;")
    con.execute("LOAD sqlite;")
    con.execute(f"ATTACH '{sqlite_path}' AS db (TYPE sqlite);")

    tables = con.execute("""
        SELECT table_name
        FROM duckdb_tables()
        WHERE database_name='db'
    """).fetchall()

    tables = [t[0] for t in tables]

    graph = nx.Graph()
    schema_texts = []

    for t in tables:
        cols = con.execute(f"PRAGMA table_info('db.{t}')").fetchall()
        col_names = [c[1] for c in cols]

        graph.add_node(t)
        schema_texts.append(
            f"{t} table with columns: {', '.join(col_names)}"
        )


    embedder = HFTextEmbedder()
    embeddings = embedder.encode(schema_texts)

    import faiss
    index = faiss.IndexFlatIP(embeddings.shape[1])
    index.add(embeddings)

    doc_tokens = [tokenize(t) for t in schema_texts]
    df = Counter()
    for toks in doc_tokens:
        for tok in set(toks):
            df[tok] += 1

    artifact = {
        "graph": graph,
        "schema_texts": schema_texts,
        "schema_ids": tables,
        "schema_text": "\n".join(schema_texts),
        "faiss_index": index,
        "doc_tokens": doc_tokens,
        "df": dict(df),
    }

    output_path = output_dir / f"{db_id}.pkl"
    with open(output_path, "wb") as f:
        pickle.dump(artifact, f)

    print(f"✅ Built schema: {output_path}")
