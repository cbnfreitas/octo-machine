from app.config import AppConfig


def scene_image_instruction_paragraph(app_config: AppConfig) -> str:
    if not app_config.scene_images_in_chat:
        return ""
    return (
        "Na **primeira entrada** a um lugar nesta sessão, o JSON de `move` pode trazer "
        "**`place_scene_image`** — a interface **mostra** essa ilustração ao jogador "
        "automaticamente; mantenha a prosa coerente com o ambiente. "
    )
