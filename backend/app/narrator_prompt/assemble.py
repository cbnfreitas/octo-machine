from app.config import AppConfig
from app.narrator_prompt.helpers import fixed_intro_context_section
from app.narrator_prompt.section_acrobatics_fatigue import acrobatics_fatigue_time_section
from app.narrator_prompt.section_layered_description import layered_description_section
from app.narrator_prompt.section_markdown_formatting import markdown_emphasis_section
from app.narrator_prompt.section_message_economy import response_length_economy_section
from app.narrator_prompt.section_player_agency import player_agency_section
from app.narrator_prompt.section_pov import pov_rules_section
from app.narrator_prompt.section_role_world import role_world_rules_section
from app.narrator_prompt.section_space_direction import spatial_direction_section
from app.narrator_prompt.section_tools_dice import tools_dice_section_body
from app.narrator_prompt.section_tools_move import tools_move_section_body


def build_rpg_sections(app_config: AppConfig) -> str:
    parts: list[str] = []
    if app_config.include_fixed_intro_context:
        parts.append(fixed_intro_context_section(app_config))
    if app_config.include_acrobatics_fatigue_time:
        parts.append(acrobatics_fatigue_time_section())
    if app_config.include_role_world_rules:
        parts.append(role_world_rules_section(app_config))
    move_tools = tools_move_section_body(app_config) if app_config.include_tools_move else ""
    dice_tools = tools_dice_section_body() if app_config.include_tools_dice else ""
    if move_tools or dice_tools:
        parts.append(f"## Ferramentas\n\n{move_tools}{dice_tools}")
    if app_config.include_player_agency:
        parts.append(player_agency_section())
    if app_config.include_layered_description:
        parts.append(layered_description_section())
    if app_config.include_spatial_direction:
        parts.append(spatial_direction_section())
    if app_config.include_response_length_economy:
        parts.append(response_length_economy_section(app_config))
    if app_config.include_pov_rules:
        parts.append(pov_rules_section())
    if app_config.include_markdown_emphasis:
        parts.append(markdown_emphasis_section())
    return "".join(parts)
