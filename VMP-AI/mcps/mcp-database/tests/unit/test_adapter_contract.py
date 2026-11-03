"""Every concrete adapter must conform to the Adapter ABC: same methods, signatures and sane capabilities.

Runs without Docker — it inspects the classes, it does not connect. A new adapter (SQLite, etc.) that
passes this test is wired correctly before a single integration test touches a real database.
"""

import inspect

import pytest

from mcp_database.adapters.base import CAPABILITY_NAMES, Adapter
from mcp_database.adapters.mongodb import MongoAdapter
from mcp_database.adapters.mysql import MySQLAdapter
from mcp_database.adapters.postgres import PostgresAdapter
from mcp_database.config import parse_connection

ADAPTERS = [
    (PostgresAdapter, "postgresql://u@h/db"),
    (MySQLAdapter, "mysql://u@h/db"),
    (MongoAdapter, "mongodb://h/db"),
]

ABSTRACT_METHODS = sorted(Adapter.__abstractmethods__)


@pytest.mark.parametrize("adapter_cls", [cls for cls, _ in ADAPTERS])
def test_no_abstract_methods_left(adapter_cls):
    """A concrete adapter implements every abstract method, so it is instantiable."""
    assert adapter_cls.__abstractmethods__ == frozenset()


@pytest.mark.parametrize("adapter_cls", [cls for cls, _ in ADAPTERS])
@pytest.mark.parametrize("method", ABSTRACT_METHODS)
def test_method_signature_matches_the_abc(adapter_cls, method):
    """Each implemented method keeps the ABC's parameter names, so the tools can call it uniformly."""
    base_params = list(inspect.signature(getattr(Adapter, method)).parameters)
    impl_params = list(inspect.signature(getattr(adapter_cls, method)).parameters)
    assert impl_params == base_params, f"{adapter_cls.__name__}.{method} diverges from the ABC"


@pytest.mark.parametrize(("adapter_cls", "uri"), ADAPTERS)
def test_capabilities_are_a_known_subset(adapter_cls, uri):
    """Declared capabilities exist in the canonical set and round-trip through the instance helpers."""
    adapter = adapter_cls(parse_connection("c", {"uri": uri}))
    assert adapter_cls.CAPABILITIES <= CAPABILITY_NAMES
    assert set(adapter.capabilities()) == adapter_cls.CAPABILITIES
    for feature in adapter_cls.CAPABILITIES:
        assert adapter.supports(feature)


@pytest.mark.parametrize(("adapter_cls", "uri"), ADAPTERS)
def test_sql_adapters_declare_a_dialect(adapter_cls, uri):
    """Any adapter that reuses the SQL estimate/probe path must set a sqlglot dialect."""
    from mcp_database.adapters.base import SQLAdapter

    if issubclass(adapter_cls, SQLAdapter):
        assert getattr(adapter_cls, "_DIALECT", None), f"{adapter_cls.__name__} lacks a _DIALECT"
