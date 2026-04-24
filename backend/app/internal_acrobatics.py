"""
Engine-side acrobatics fatigue (0–100). Only qualitative labels go to the narrator channel.
"""

from __future__ import annotations

# Maintainer map (thresholds are engine-only; labels are what the LLM sees):
#   0%     — Plenamente descansado
#   (0,12] — Um pouco cansado  (10% lands here)
#   (12,28] — Cansaço moderado
#   (28,45] — Visivelmente fatigado
#   (45,62] — Muito cansado; o corpo pede pausa
#   (62,78] — Limite operacional; falta de precisão e estabilidade
#   (78,92] — À beira do esgotamento
#   (92,100) — Quase colapsando
#   100%   — Exausto — desmaio iminente ou incapacidade de prosseguir com segurança


def fatigue_label_for_context(percent: float) -> str:
    p = max(0.0, min(100.0, float(percent)))
    if p == 0:
        return "Plenamente descansado."
    if p <= 12:
        return "Um pouco cansado."
    if p <= 28:
        return "Cansaço moderado."
    if p <= 45:
        return "Visivelmente fatigado."
    if p <= 62:
        return "Muito cansado; o corpo pede pausa."
    if p <= 78:
        return "Limite operacional; falta de precisão e estabilidade."
    if p <= 92:
        return "À beira do esgotamento."
    if p < 100:
        return "Quase colapsando."
    return "Exausto — desmaio iminente ou incapacidade de prosseguir com segurança."
