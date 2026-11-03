from __future__ import annotations

from psycopg import sql

_VECTOR_OPERATORS = {"cosine": "<=>", "l2": "<->", "inner_product": "<#>", "l1": "<+>"}


_VECTOR_OPCLASSES = {
    "cosine": "vector_cosine_ops",
    "l2": "vector_l2_ops",
    "inner_product": "vector_ip_ops",
    "l1": "vector_l1_ops",
}


_VECTOR_INDEX_OPTIONS = {"hnsw": frozenset({"m", "ef_construction"}), "ivfflat": frozenset({"lists"})}


def _qualified(schema: str, obj: str) -> sql.Composed:
    """schema.object as a safely quoted psycopg Composed identifier."""
    return sql.SQL("{}.{}").format(sql.Identifier(schema), sql.Identifier(obj))
