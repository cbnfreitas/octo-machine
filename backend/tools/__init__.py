import json
from collections.abc import Callable

from openai.types.chat import ChatCompletionToolUnionParam

from .action_outcome import TOOL as ACTION_OUTCOME_TOOL
from .action_outcome import TOOL_SYSTEM_INSTRUCTION as ACTION_OUTCOME_INSTRUCTION
from .action_outcome import run as run_action_outcome
from .random_integer import TOOL as RANDOM_INTEGER_TOOL
from .random_integer import TOOL_SYSTEM_INSTRUCTION as RANDOM_INTEGER_INSTRUCTION
from .random_integer import run as run_random_integer
from .toss_coin import TOOL as TOSS_COIN_TOOL
from .toss_coin import TOOL_SYSTEM_INSTRUCTION as TOSS_COIN_INSTRUCTION
from .toss_coin import run as run_toss_coin

_TOOL_SPECS: list[
    tuple[str, ChatCompletionToolUnionParam, str, Callable[[str], str]]
] = [
    ("action_outcome", ACTION_OUTCOME_TOOL, ACTION_OUTCOME_INSTRUCTION, run_action_outcome),
    ("random_integer", RANDOM_INTEGER_TOOL, RANDOM_INTEGER_INSTRUCTION, run_random_integer),
    ("toss_coin", TOSS_COIN_TOOL, TOSS_COIN_INSTRUCTION, run_toss_coin),
]

TOOLS: list[ChatCompletionToolUnionParam] = [spec[1] for spec in _TOOL_SPECS]

_RUNNERS: dict[str, Callable[[str], str]] = {spec[0]: spec[3] for spec in _TOOL_SPECS}


def combined_tool_instructions() -> str:
    return "\n\n".join(spec[2] for spec in _TOOL_SPECS)


def run_tool(name: str, arguments_json: str) -> str:
    runner = _RUNNERS.get(name)
    if runner is None:
        return json.dumps({"error": f"Unknown tool: {name}"})
    return runner(arguments_json)
