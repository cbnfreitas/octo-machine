from app.config import AppConfig

FULL_NARRATOR_APP_CONFIG = AppConfig(
    include_narrator_system_prompt_md=True,
    include_tools_move=True,
    include_tools_dice=True,
    include_final_checklist_reminder=True,
)
