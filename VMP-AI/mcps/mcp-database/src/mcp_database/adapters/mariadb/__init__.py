from typing import ClassVar

from ..mysql import MySQLAdapter


class MariaDBAdapter(MySQLAdapter):
    """MariaDB speaks the MySQL protocol and dialect; the subclass keeps the engine identity honest."""

    _SHOW_REPLICAS = "SHOW SLAVE HOSTS"
    _USERS_SELECT = "SELECT user, host, plugin, password_expired FROM mysql.user"
    _STATUS_ALIASES: ClassVar[dict[str, str]] = {
        "Source_Host": "Master_Host",
        "Replica_IO_Running": "Slave_IO_Running",
        "Replica_SQL_Running": "Slave_SQL_Running",
        "Seconds_Behind_Source": "Seconds_Behind_Master",
    }

    def _timeout_statement(self) -> str:
        """MariaDB has no max_execution_time; max_statement_time takes seconds and bounds all statements."""
        return f"SET SESSION max_statement_time = {self.config.query_timeout_s}"
