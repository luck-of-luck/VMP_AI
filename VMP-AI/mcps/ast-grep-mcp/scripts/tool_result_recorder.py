"""Shared tool-run result recording for scripts that batch-invoke MCP tools."""

from typing import Any, Dict, Optional

ERROR_MESSAGE_MAX_LEN = 500
STRING_RESULT_PREVIEW_LEN = 200
OTHER_RESULT_STR_LEN = 300
DICT_KEYS_PREVIEW = 10


def record_tool_result(
    results: Dict[str, Dict[str, Any]],
    name: str,
    result: Any = None,
    error: Optional[BaseException] = None,
    skipped: Optional[str] = None,
    include_string_preview: bool = True,
    include_other_fallback: bool = True,
) -> None:
    """Record a tool invocation outcome into a results dict.

    Captures OK/ERROR/SKIPPED status plus a flattened summary of the result:
    dict values become scalar/count/keys entries; lists get a count; strings
    get a length (and preview when enabled).
    """
    entry: Dict[str, Any] = {"tool": name}

    if skipped:
        entry["status"] = "SKIPPED"
        entry["reason"] = skipped
    elif error:
        entry["status"] = "ERROR"
        entry["error"] = str(error)[:ERROR_MESSAGE_MAX_LEN]
    else:
        entry["status"] = "OK"
        if isinstance(result, dict):
            entry["result_keys"] = list(result.keys())
            for key, value in result.items():
                if key == "status":
                    continue
                if isinstance(value, (int, float, str, bool)):
                    entry[key] = value
                elif isinstance(value, list):
                    entry[f"{key}_count"] = len(value)
                elif isinstance(value, dict):
                    entry[f"{key}_keys"] = list(value.keys())[:DICT_KEYS_PREVIEW]
        elif isinstance(result, list):
            entry["result_count"] = len(result)
        elif isinstance(result, str):
            entry["result_length"] = len(result)
            if include_string_preview:
                entry["result_preview"] = result[:STRING_RESULT_PREVIEW_LEN]
        elif include_other_fallback:
            entry["result"] = str(result)[:OTHER_RESULT_STR_LEN]

    results[name] = entry
