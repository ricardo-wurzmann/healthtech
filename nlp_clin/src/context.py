from __future__ import annotations
import re

NEG_PATTERNS = [
    r"\bnega\b",
    r"\bnegou\b",
    r"\bsem\b",
    r"\bnao\s+tem\b",
    r"\bnao\s+apresenta\b",
    r"\bsem\s+queixas?\b",
]

POSSIBLE_PATTERNS = [
    r"\bsuspeita\b",
    r"\bhipotese\b",
    r"\bpossivel\b",
    r"\bprovavel\b",
]

HIST_PATTERNS = [
    r"\bhist(ó|o)ria\s+de\b",
    r"\bantecedentes?\b",
    r"\bpassado\b",
    r"\bhpp\b",
]

def classify_assertion(sentence: str) -> str:
    s = sentence.lower()

    if any(re.search(p, s) for p in NEG_PATTERNS):
        return "NEGATED"
    if any(re.search(p, s) for p in POSSIBLE_PATTERNS):
        return "POSSIBLE"
    if any(re.search(p, s) for p in HIST_PATTERNS):
        return "HISTORICAL"
    return "PRESENT"
