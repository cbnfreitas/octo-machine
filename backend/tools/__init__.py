import json

from openai.types.chat import ChatCompletionToolUnionParam

from app.session_state import GameSessionState

from .action_outcome import TOOL as ACTION_OUTCOME_TOOL
from .action_outcome import TOOL_SYSTEM_INSTRUCTION as ACTION_OUTCOME_INSTRUCTION
from .action_outcome import run as run_action_outcome
from .move import TOOL as MOVE_TOOL
from .move import TOOL_SYSTEM_INSTRUCTION as MOVE_INSTRUCTION
from .move import run as run_move
from .random_integer import TOOL as RANDOM_INTEGER_TOOL
from .random_integer import TOOL_SYSTEM_INSTRUCTION as RANDOM_INTEGER_INSTRUCTION
from .random_integer import run as run_random_integer
from .toss_coin import TOOL as TOSS_COIN_TOOL
from .toss_coin import TOOL_SYSTEM_INSTRUCTION as TOSS_COIN_INSTRUCTION
from .toss_coin import run as run_toss_coin

_TOOL_SPECS: list[tuple[str, ChatCompletionToolUnionParam, str]] = [
    ("action_outcome", ACTION_OUTCOME_TOOL, ACTION_OUTCOME_INSTRUCTION),
    ("move", MOVE_TOOL, MOVE_INSTRUCTION),
    ("random_integer", RANDOM_INTEGER_TOOL, RANDOM_INTEGER_INSTRUCTION),
    ("toss_coin", TOSS_COIN_TOOL, TOSS_COIN_INSTRUCTION),
]

TOOLS: list[ChatCompletionToolUnionParam] = [spec[1] for spec in _TOOL_SPECS]


def combined_tool_instructions() -> str:
    return "\n\n".join(spec[2] for spec in _TOOL_SPECS)


async def run_tool(
    name: str,
    arguments_json: str,
    *,
    session_state: GameSessionState | None = None,
) -> str:
    if name == "move":
        return run_move(arguments_json, session_state=session_state)
    if name == "action_outcome":
        return run_action_outcome(arguments_json)
    if name == "random_integer":
        return run_random_integer(arguments_json)
    if name == "toss_coin":
        return run_toss_coin(arguments_json)
    return json.dumps({"error": f"Unknown tool: {name}"})
