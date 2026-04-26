import json

from openai.types.chat import ChatCompletionToolUnionParam

from app.config import AppConfig
from app.session_state import GameSessionState

from .roll_dice import TOOL as ROLL_DICE_TOOL
from .roll_dice import TOOL_SYSTEM_INSTRUCTION as ROLL_DICE_INSTRUCTION
from .roll_dice import run as run_roll_dice
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
    ("roll_dice", ROLL_DICE_TOOL, ROLL_DICE_INSTRUCTION),
    ("move", MOVE_TOOL, MOVE_INSTRUCTION),
    ("random_integer", RANDOM_INTEGER_TOOL, RANDOM_INTEGER_INSTRUCTION),
    ("toss_coin", TOSS_COIN_TOOL, TOSS_COIN_INSTRUCTION),
]


def _active_narrator_tool_specs(app_config: AppConfig) -> list[tuple[str, ChatCompletionToolUnionParam, str]]:
    out: list[tuple[str, ChatCompletionToolUnionParam, str]] = []
    for name, tool, instr in _TOOL_SPECS:
        if name == "move" and not app_config.include_tools_move:
            continue
        if name == "roll_dice" and not app_config.include_tools_dice:
            continue
        out.append((name, tool, instr))
    return out


def narrator_tools(app_config: AppConfig) -> list[ChatCompletionToolUnionParam]:
    return [spec[1] for spec in _active_narrator_tool_specs(app_config)]


def combined_tool_instructions(app_config: AppConfig) -> str:
    return "\n\n".join(spec[2] for spec in _active_narrator_tool_specs(app_config))


async def run_tool(
    name: str,
    arguments_json: str,
    *,
    session_state: GameSessionState | None = None,
) -> str:
    if name == "move":
        return run_move(arguments_json, session_state=session_state)
    if name == "roll_dice":
        return run_roll_dice(arguments_json)
    if name == "random_integer":
        return run_random_integer(arguments_json)
    if name == "toss_coin":
        return run_toss_coin(arguments_json)
    return json.dumps({"error": f"Unknown tool: {name}"})
