import json
from collections.abc import Callable
from typing import Any

from app.logging_config import logger, yellow_tool


def invoke_tool(
    tool_name: str,
    arguments_json: str,
    execute: Callable[[dict[str, Any]], dict[str, object]],
    *,
    log_line: Callable[[dict[str, object]], str] | None = None,
) -> str:
    try:
        raw = json.loads(arguments_json) if arguments_json else {}
    except json.JSONDecodeError as e:
        logger.warning(
            "%s bad JSON arguments_json=%r err=%s",
            yellow_tool(tool_name),
            arguments_json,
            e,
        )
        return json.dumps({"error": f"Invalid tool arguments JSON: {e}"})

    if not isinstance(raw, dict):
        logger.warning(
            "%s bad args (not an object) raw=%r arguments_json=%r",
            yellow_tool(tool_name),
            raw,
            arguments_json,
        )
        return json.dumps({"error": "Tool arguments must be a JSON object"})

    args: dict[str, Any] = raw
    try:
        result = execute(args)
    except (KeyError, TypeError, ValueError) as e:
        logger.warning(
            "%s bad args parsed=%r arguments_json=%r err=%s",
            yellow_tool(tool_name),
            args,
            arguments_json,
            e,
        )
        return json.dumps({"error": f"Invalid {tool_name} args: {e}"})

    if log_line:
        logger.info("[%s] %s", yellow_tool(tool_name), log_line(result))
    else:
        logger.info("[%s] %s", yellow_tool(tool_name), result)

    return json.dumps(result)
