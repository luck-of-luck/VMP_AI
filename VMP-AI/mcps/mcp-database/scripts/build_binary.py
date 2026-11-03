"""Single source of truth for the PyInstaller build (see `make bin` and the CI `binaries` job).

Adapters are imported lazily by `create_adapter`, so PyInstaller's static analysis cannot find them:
every driver is collected explicitly here. A dropped entry ships a binary that is silently broken for
that engine, so keep this list complete when adding an engine.
"""

import PyInstaller.__main__

_DRIVERS = (
    "psycopg", "psycopg_binary", "psycopg_pool", "aiomysql",
    "pymongo", "bson", "aiosqlite", "redis", "cryptography",
)  # fmt: skip

ARGS = [
    "--onefile",
    "--name",
    "mcp-database",
    "--clean",
    "--noconfirm",
    "--collect-submodules",
    "mcp_database",
    "--collect-submodules",
    "sqlglot",
    *[flag for driver in _DRIVERS for flag in ("--collect-all", driver)],
    "--paths",
    "src",
    "scripts/bin_entry.py",
]


if __name__ == "__main__":
    PyInstaller.__main__.run(ARGS)
