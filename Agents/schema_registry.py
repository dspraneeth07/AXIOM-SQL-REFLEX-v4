import pickle
from pathlib import Path
from collections import Counter

from agents.cartographer import tokenize
from agents.embeddings import HFTextEmbedder

# =========================================================
# CONFIG
# =========================================================

SCHEMA_ROOT = Path("../schemas")

# =========================================================
# LIGHTWEIGHT RUNTIME SINGLETONS
# (SAFE: tokenizer + small HF model only)
# =========================================================

_EMBEDDER = HFTextEmbedder()

# =========================================================
# SCHEMA LOADER (PURE, FAST, NON-BLOCKING)
# =========================================================

def load_schema_for_db(db_id: str, dataset: str) -> dict:
    """
    Load schema artifacts for a given database.

    dataset: "spider" | "bird"
    db_id: database id (e.g. academic, concert_singer, etc.)
    """

    schema_path = SCHEMA_ROOT / dataset / f"{db_id}.pkl"

    if not schema_path.exists():
        raise FileNotFoundError(
            f"Schema not found for {dataset}/{db_id} "
            f"at {schema_path}"
        )

    # -------------------------------
    # LOAD PICKLED ARTIFACT (PURE DATA)
    # -------------------------------
    with open(schema_path, "rb") as f:
        schema = pickle.load(f)

    # -------------------------------
    # REQUIRED STRUCTURE VALIDATION
    # -------------------------------

    if "schema_texts" not in schema:
        raise ValueError(f"{dataset}/{db_id}: missing schema_texts")

    if "graph" not in schema:
        raise ValueError(f"{dataset}/{db_id}: missing graph")

    if "faiss_index" not in schema:
        raise ValueError(f"{dataset}/{db_id}: missing faiss_index")

    # -------------------------------
    # BACKWARD / FORWARD PATCHING
    # -------------------------------

    if "schema_ids" not in schema:
        schema["schema_ids"] = list(range(len(schema["schema_texts"])))

    if "schema_text" not in schema:
        schema["schema_text"] = "\n".join(schema["schema_texts"])

    if "doc_tokens" not in schema or "df" not in schema:
        doc_tokens = [tokenize(t) for t in schema["schema_texts"]]
        df = Counter()
        for toks in doc_tokens:
            for t in set(toks):
                df[t] += 1
        schema["doc_tokens"] = doc_tokens
        schema["df"] = dict(df)

    # -------------------------------
    # ATTACH SAFE RUNTIME OBJECTS
    # -------------------------------

    schema["embedder"] = _EMBEDDER

    # -------------------------------
    # FINAL CONTRACT CHECK
    # -------------------------------

    required_keys = {
        "graph",
        "schema_texts",
        "schema_ids",
        "schema_text",
        "faiss_index",
        "doc_tokens",
        "df",
        "embedder",
    }

    missing = required_keys - schema.keys()
    if missing:
        raise ValueError(
            f"{dataset}/{db_id} schema corrupted. Missing: {missing}"
        )

    return schema
