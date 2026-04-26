from app.narrator_prompt.helpers import secret_reveal_hard_rule


def final_checklist_reminder_section() -> str:
    return (
        "## Lembrete final (repetição; confere antes de enviar)\n\n"
        "**POV e consistência:** narra em **segunda pessoa** só o que o personagem percebe **neste** "
        "instante (vê, ouve, cheira, tato no limite do natural); **sem** voz de autor do mapa, **sem** "
        "metaconhecimento do ficheiro JSON; **não** contradiz o **ENGINE_CONTEXT** nem as **fichas de "
        "cena**.\n\n"
        "**Segredos e `roll_dice`:** não reveles o que o mapa ainda não libertou por ação "
        "pertinente ou teste bem sucedido. Se o resultado for **falha** ou **falha crítica** numa busca "
        "ou percepção incerta, fica em **inconclusão**; **não** confirmes alvos ocultos nem **traga para a "
        "prosa** termos que só estavam no parâmetro **`skill`** (é metadado da tool, não fala ao jogador).\n\n"
        f"**{secret_reveal_hard_rule()}**"
    )
