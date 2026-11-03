from ..config import ConnectionConfig
from .base import Adapter


def create_adapter(config: ConnectionConfig) -> Adapter:
    """Instantiate the adapter for the connection's database type (driver imported lazily)."""
    if config.type == "postgres":
        from .postgres import PostgresAdapter

        return PostgresAdapter(config)
    if config.type == "mysql":
        from .mysql import MySQLAdapter

        return MySQLAdapter(config)
    if config.type == "mariadb":
        from .mariadb import MariaDBAdapter

        return MariaDBAdapter(config)
    if config.type == "sqlite":
        from .sqlite import SQLiteAdapter

        return SQLiteAdapter(config)
    if config.type == "redis":
        from .redis import RedisAdapter

        return RedisAdapter(config)
    from .mongodb import MongoAdapter

    return MongoAdapter(config)


__all__ = ["Adapter", "create_adapter"]
