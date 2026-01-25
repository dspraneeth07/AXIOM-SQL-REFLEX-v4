from typing import List, Dict, Any, TypedDict

class CartographerOutput(TypedDict):
    tables: List[str]
    joins: List[str]
    confidence: float

class ArchitectOutput(TypedDict):
    sql: str
    intent: str  # READ / WRITE
    expected_shape: str  # single-row, multi-row

class CriticOutput(TypedDict):
    ok: bool
    confidence: float
    reason: str
