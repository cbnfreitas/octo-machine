import json
import logging

from openai.types.chat import ChatCompletionToolUnionParam

log = logging.getLogger(__name__)

from .random_integer import TOOL as RANDOM_INTEGER_TOOL
from .random_integer import run as run_random_integer

TOOLS: list[ChatCompletionToolUnionParam] = [RANDOM_INTEGER_TOOL]


def run_tool(name: str, arguments_json: str) -> str:
    log.info("Tool call: %s %s", name, arguments_json)
    if name == "random_integer":
        return run_random_integer(arguments_json)
    return json.dumps({"error": f"Unknown tool: {name}"})
