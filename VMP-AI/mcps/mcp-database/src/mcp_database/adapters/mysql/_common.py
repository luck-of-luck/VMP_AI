from __future__ import annotations


def _ident(name: str) -> str:
    """Backtick-quote an identifier, doubling embedded backticks."""
    return "`" + name.replace("`", "``") + "`"


def _qualified(database: str, obj: str) -> str:
    """database.object with both parts backtick-quoted."""
    return f"{_ident(database)}.{_ident(obj)}"
