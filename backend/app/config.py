from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel


def game_assets_root() -> Path:
    """Directory served at `/game` (see FastAPI StaticFiles mount)."""
    return Path(__file__).resolve().parent / "game"


def prompts_root() -> Path:
    """Static narrator prompt fragments; sibling of ``tools/`` under ``backend/``."""
    return Path(__file__).resolve().parent.parent / "prompts"


class AppConfig(BaseModel):
    game_folder: str = "uma_noite_de_trabalho"

    narration_initial_max_chars: int = 1000
    narration_followup_max_chars: int = 500

    include_role_world_rules: bool = True

    include_fixed_intro_context: bool = True
    include_acrobatics_fatigue_time: bool = False
    
    include_tools_move: bool = False
    include_tools_dice: bool = False
    include_player_agency: bool = False
    include_layered_description: bool = False
    include_spatial_direction: bool = False
    include_response_length_economy: bool = False
    include_pov_rules: bool = False
    include_markdown_emphasis: bool = False
    include_final_checklist_reminder: bool = False
    scene_images_in_chat: bool = False

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
