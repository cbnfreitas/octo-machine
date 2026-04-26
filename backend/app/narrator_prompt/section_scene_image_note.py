from app.config import NarratorPromptConfig


def scene_image_instruction_paragraph(config: NarratorPromptConfig) -> str:
    if not config.scene_images_in_chat:
        return ""
    return (
        "Na **primeira entrada** a um lugar nesta sessão, o JSON de `move` pode trazer "
        "**`place_scene_image`** — a interface **mostra** essa ilustração ao jogador "
        "automaticamente; mantenha a prosa coerente com o ambiente. "
    )
