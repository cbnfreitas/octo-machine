from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field


def game_assets_root() -> Path:
    """Directory served at `/game` (see FastAPI StaticFiles mount)."""
    return Path(__file__).resolve().parent / "game"


class NarratorPromptConfig(BaseModel):
    """System prompt for the narrator LLM: section toggles and reply budgets."""

    narration_initial_max_chars: int = 1000
    narration_followup_max_chars: int = 500

    scene_images_in_chat: bool = False

    include_fixed_intro_context: bool = True
    include_acrobatics_fatigue_time: bool = True
    include_role_world_rules: bool = True
    include_tools_move: bool = True
    include_tools_dice: bool = True
    include_player_agency: bool = True
    include_layered_description: bool = True
    include_spatial_direction: bool = True
    include_response_length_economy: bool = True
    include_pov_rules: bool = True
    include_markdown_emphasis: bool = True
    include_final_checklist_reminder: bool = True


class AppConfig(BaseModel):
    """Root application settings, split by domain. Extend with new sections as needed."""

    game_folder: str = "uma_noite_de_trabalho"
    narrator_prompt: NarratorPromptConfig = Field(default_factory=NarratorPromptConfig)

    @property
    def game_package_root(self) -> Path:
        return game_assets_root() / self.game_folder

    @property
    def game_map_json_path(self) -> Path:
        return self.game_package_root / f"{self.game_folder}.json"

    @property
    def game_scene_images_dir(self) -> Path:
        return self.game_package_root / "imgs"


@lru_cache(maxsize=1)
def get_app_config() -> AppConfig:
    return AppConfig()


def get_narrator_prompt_config() -> NarratorPromptConfig:
    return get_app_config().narrator_prompt
