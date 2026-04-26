from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel


def game_assets_root() -> Path:
    """Directory served at `/game` (see FastAPI StaticFiles mount)."""
    return Path(__file__).resolve().parent / "game"


class AppConfig(BaseModel):
    """Application settings (game package, narrator prompt toggles, reply budgets)."""

    game_folder: str = "uma_noite_de_trabalho"

    narration_initial_max_chars: int = 1000
    narration_followup_max_chars: int = 500

    scene_images_in_chat: bool = False

    include_fixed_intro_context: bool = False
    include_acrobatics_fatigue_time: bool = False
    include_role_world_rules: bool = False
    include_tools_move: bool = False
    include_tools_dice: bool = False
    include_player_agency: bool = False
    include_layered_description: bool = False
    include_spatial_direction: bool = False
    include_response_length_economy: bool = False
    include_pov_rules: bool = False
    include_markdown_emphasis: bool = False
    include_final_checklist_reminder: bool = False

    @property
    def game_package_root(self) -> Path:
        return game_assets_root() / self.game_folder

    @property
    def game_map_json_path(self) -> Path:
        return self.game_package_root / f"{self.game_folder}.json"

    @property
    def game_scene_images_dir(self) -> Path:
        return self.game_package_root / "imgs"


def app_config_with_full_narrator_sections() -> AppConfig:
    """All narrator sections and tools on; use in tests or legacy-style prompts."""
    return AppConfig(
        include_fixed_intro_context=True,
        include_acrobatics_fatigue_time=True,
        include_role_world_rules=True,
        include_tools_move=True,
        include_tools_dice=True,
        include_player_agency=True,
        include_layered_description=True,
        include_spatial_direction=True,
        include_response_length_economy=True,
        include_pov_rules=True,
        include_markdown_emphasis=True,
        include_final_checklist_reminder=True,
    )


@lru_cache(maxsize=1)
def get_app_config() -> AppConfig:
    return AppConfig()
