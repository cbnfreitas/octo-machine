from functools import lru_cache

from pydantic import BaseModel, Field

from app.feature_flags import scene_images_enabled


class NarratorPromptConfig(BaseModel):
    """System prompt for the narrator LLM: section toggles and reply budgets."""

    narration_initial_max_chars: int = 1000
    narration_followup_max_chars: int = 500

    scene_images_in_chat: bool = Field(default_factory=scene_images_enabled)

    include_fixed_intro_context: bool = True
    include_acrobatics_fatigue_time: bool = True
    include_role_world_rules: bool = True
    include_tools_move_and_dice: bool = True
    include_player_agency: bool = True
    include_layered_description: bool = True
    include_spatial_direction: bool = True
    include_response_length_economy: bool = True
    include_pov_rules: bool = True
    include_markdown_emphasis: bool = True
    include_final_checklist_reminder: bool = True


class AppConfig(BaseModel):
    """Root application settings, split by domain. Extend with new sections as needed."""

    narrator_prompt: NarratorPromptConfig = Field(default_factory=NarratorPromptConfig)


@lru_cache(maxsize=1)
def get_app_config() -> AppConfig:
    return AppConfig()


def get_narrator_prompt_config() -> NarratorPromptConfig:
    return get_app_config().narrator_prompt
