from app.session_state import GameSessionState
from tools.move import _description_for_player_facing, place_details_for_engine_context


def test_description_for_player_facing_keeps_secret_blocks() -> None:
    raw = (
        "A escada começa a oeste e curva-se para o norte. "
        "Segredo difícil: pequena abertura de ventilação quase invisível."
    )

    result = _description_for_player_facing(raw)

    assert "Segredo difícil:" in result
    assert "abertura de ventilação" in result


def test_place_details_for_engine_context_uses_raw_map_text() -> None:
    state = GameSessionState()

    perceptible, authoring = place_details_for_engine_context(
        "Vestíbulo",
        session_state=state,
    )

    assert perceptible
    assert authoring
    assert perceptible == authoring
    assert "Segredo difícil:" in perceptible
