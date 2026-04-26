from app.config import AppConfig

FULL_NARRATOR_APP_CONFIG = AppConfig(
    include_narrator_system_prompt_md=False,
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
