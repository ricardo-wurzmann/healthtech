from __future__ import annotations
import re

_RE_MULTISPACE = re.compile(r"[ \t]+")
_RE_MULTINEWLINE = re.compile(r"\n{3,}")

def normalize_text(text: str) -> str:
    # Normaliza quebras e espaços
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _RE_MULTINEWLINE.sub("\n\n", text)
    text = _RE_MULTISPACE.sub(" ", text)

    # Padroniza alguns formatos comuns de PS (pressão, temperatura, etc.)
    # Ex: 120x70 -> 120 x 70 (não explode tudo, só quando parece PA)
    text = re.sub(r"(\d{2,3})\s*[xX/]\s*(\d{2,3})", r"\1 x \2", text)

    # Espaços ao redor de pontuação básica (sem destruir acentos)
    text = re.sub(r"\s+([,;:.])", r"\1", text)
    text = re.sub(r"([,;:])(\S)", r"\1 \2", text)

    return text.strip()
