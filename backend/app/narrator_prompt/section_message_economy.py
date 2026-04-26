from app.config import AppConfig


def response_length_economy_section(app_config: AppConfig) -> str:
    initial = app_config.narration_initial_max_chars
    followup = app_config.narration_followup_max_chars
    return (
        "## Economia de detalhe (extensão)\n\n"
        "Controle o **tamanho** de cada resposta (contagem aproximada por você antes de enviar):\n\n"
        "- **Descrições iniciais** — primeira vez que **firme** um **lugar** (p.ex. após `move`), ou "
        f"que **apresente** uma **pessoa** relevante ou um **evento** que vira a cena: **até "
        f"~{initial} caracteres**. Priorize uma imagem nítida, ganchos espaciais e "
        "tom; **sem** inventário nem parágrafos longos.\n"
        "- **Follow-up** — continuação na **mesma** situação (pergunta pontual do jogador, reação "
        f"imediata, detalhe pedido, micro-consequência): **até ~{followup} "
        "caracteres**.\n"
        "- **Retorno ou permanência no mesmo cômodo** — se a sua própria prosa recente já descreveu o "
        "ambiente e **nada** de importante mudou, a próxima mensagem **não** vira segundo arranque: "
        "trate como follow-up **extra curto** (incluindo após `move` com **`revisit`: true**). "
        "**Proibido** usar o teto de caracteres só para repetir mesa, forno, utensílios ou cheiros que "
        "já estavam estáveis.\n\n"
        "Se pedirem **mais**, novo bloco dentro do mesmo teto. Só alongue de forma excecional quando o "
        "jogador pedir explicitamente mais texto ou quando a tensão exigir **um** parágrafo extra—e "
        "mesmo assim com moderação.\n\n"
    )
