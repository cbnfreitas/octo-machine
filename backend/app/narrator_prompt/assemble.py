from app.config import AppConfig
from tools.move import load_narrator_system_prompt_rendered


def build_rpg_sections(app_config: AppConfig) -> str:
    if app_config.include_narrator_system_prompt_md:
        return load_narrator_system_prompt_rendered()
    return ""
