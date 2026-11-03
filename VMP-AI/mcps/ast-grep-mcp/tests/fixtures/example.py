from typing import Any

from ast_grep_mcp.utils.console_logger import console


def hello() -> None:
    console.log("Hello, World!")


def add(a: Any, b: Any) -> Any:
    return a + b


class Calculator:
    def multiply(self, x: Any, y: Any) -> Any:
        return x * y
