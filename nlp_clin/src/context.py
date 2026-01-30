# context.py
# Rule-based assertion classifier (PT-BR clinical)
# - Entity-level (span-based) assertion
# - Left window only
# - Scope breaking (mas/porém/pontuação/etc.)
# - Trigger sets for NEGATED / POSSIBLE / HISTORICAL
#
# Usage:
#   assertion = classify_assertion(sentence, ent_start, ent_end, ent_type)

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Pattern, Tuple, Optional


# ----------------------------
# Public API
# ----------------------------

ASSERTION_PRESENT = "PRESENT"
ASSERTION_NEGATED = "NEGATED"
ASSERTION_POSSIBLE = "POSSIBLE"
ASSERTION_HISTORICAL = "HISTORICAL"


def classify_assertion(sentence: str, ent_start: int, ent_end: int, ent_type: str) -> str:
    """
    Classify entity assertion within a sentence using rule-based context.

    Args:
        sentence: sentence text
        ent_start/ent_end: entity offsets relative to sentence
        ent_type: one of SYMPTOM/PROBLEM/TEST/DRUG/PROCEDURE/ANATOMY (as per your schema)

    Returns:
        One of: PRESENT, NEGATED, POSSIBLE, HISTORICAL
    """

    # 1) Hard rule: anatomy is not negated
    if _norm_type(ent_type) == "ANATOMY":
        return ASSERTION_PRESENT

    # 2) Defensive checks
    if not sentence or ent_start is None or ent_end is None:
        return ASSERTION_PRESENT
    ent_start = max(0, min(ent_start, len(sentence)))
    ent_end = max(ent_start, min(ent_end, len(sentence)))

    # 3) Prepare contexts
    sent_lc = _norm(sentence)
    # Left window only (chars). Keep it simple and robust.
    left_raw = sent_lc[max(0, ent_start - CONFIG.left_window_chars): ent_start]

    # 4) Cut left context by last breaker within the window
    left = _cut_after_last_breaker(left_raw)

    # 5) Also check immediate "right" patterns for classic "negation before verb"
    # E.g., "não apresenta dor", "não refere vômitos" -> "não apresenta" is left-side anyway,
    # but we keep patterns generic in trigger sets.

    # 6) Evaluate triggers with precedence: NEG > POSS > HIST > PRESENT
    # We pick the closest match to entity (highest index) for each category,
    # then choose by precedence.
    scores = {
        ASSERTION_NEGATED: _best_trigger_pos(left, TRIGGERS.neg),
        ASSERTION_POSSIBLE: _best_trigger_pos(left, TRIGGERS.possible),
        ASSERTION_HISTORICAL: _best_trigger_pos(left, TRIGGERS.hist),
    }

    # If any trigger matched, return by precedence (not by closeness across categories),
    # but only if matched at all.
    if scores[ASSERTION_NEGATED] is not None:
        return ASSERTION_NEGATED
    if scores[ASSERTION_POSSIBLE] is not None:
        return ASSERTION_POSSIBLE
    if scores[ASSERTION_HISTORICAL] is not None:
        return ASSERTION_HISTORICAL

    return ASSERTION_PRESENT


# ----------------------------
# Configuration / Triggers
# ----------------------------

@dataclass(frozen=True)
class Config:
    left_window_chars: int = 60


CONFIG = Config()


def _compile_many(patterns: List[str]) -> List[Pattern]:
    return [re.compile(p, re.IGNORECASE) for p in patterns]


@dataclass(frozen=True)
class TriggerSets:
    neg: List[Pattern]
    possible: List[Pattern]
    hist: List[Pattern]


# Breakers (scope boundaries) in PT-BR clinical text
# - Strong punctuation + common contrastive connectives
BREAKERS_RE = re.compile(
    r"(\.|\;|\:|\n|\bmas\b|\bpor[eé]m\b|\bcontudo\b|\bentretanto\b|\bno entanto\b|\btodavia\b|\bpor outro lado\b)",
    re.IGNORECASE,
)

# Trigger patterns
# NOTE: keep them in LOWER/robust format (we normalize sentence anyway).
NEG_TRIGGERS = [
    # direct negation verbs
    r"\bnega(?:ndo|do|)\b",
    r"\bnegou\b",
    r"\bnegava\b",
    r"\bnega\s+queix(?:a|as)\b",
    r"\bnega\s+sintomas?\b",
    r"\bnega\s+(?:dor|febre|dispneia|vomitos?|n[aã]useas?)\b",  # small boost for common terms

    # "sem" patterns
    r"\bsem\b",
    r"\bsem\s+sinais?\s+de\b",
    r"\bsem\s+evid[eê]ncia\s+de\b",
    r"\bsem\s+queixas?\s+de\b",

    # "não" patterns
    r"\bn[aã]o\b",
    r"\bn[aã]o\s+(apresenta|refere|relata|tem|possui|evidencia)\b",
    r"\bn[aã]o\s+houve\b",
    r"\bn[aã]o\s+nega\b",  # rare, but better caught

    # absence words
    r"\bausent[ea]s?\b",
    r"\binexistente\b",
    r"\bnega(?:tivo|tiva|)\b",  # lab-style wording sometimes leaks into notes
]

POSSIBLE_TRIGGERS = [
    r"\bsuspeit[ae]\b",
    r"\bhip[oó]teses?\b",
    r"\bprov[aá]vel\b",
    r"\bposs[ií]vel\b",
    r"\bcompat[ií]vel\s+com\b",
    r"\ba\s+esclarecer\b",
    r"\ba\s+confirmar\b",
    r"\bdiferencial\b",
    r"\bddx\b",
    r"\?\s*$",  # question mark at end of left context (weak signal)
]

HIST_TRIGGERS = [
    r"\bhist[oó]ria\s+de\b",
    r"\bantecedentes?\b",
    r"\bantecedentes?\s+pessoais\b",
    r"\bhpp\b",
    r"\bap\s*:\b",
    r"\baf\s*:\b",
    r"\bpreviamente\b",
    r"\banteriormente\b",
    r"\bpr[eé]vio\b",
]

TRIGGERS = TriggerSets(
    neg=_compile_many(NEG_TRIGGERS),
    possible=_compile_many(POSSIBLE_TRIGGERS),
    hist=_compile_many(HIST_TRIGGERS),
)


# ----------------------------
# Helpers
# ----------------------------

def _norm(s: str) -> str:
    # Keep it simple: lowercase + collapse whitespace
    s = s.lower()
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def _norm_type(t: str) -> str:
    return (t or "").strip().upper()


def _cut_after_last_breaker(left_context: str) -> str:
    """
    Cuts everything before the last breaker occurrence in the left context,
    enforcing local scope (e.g., "sem X, porém Y" -> for Y, ignore "sem X").
    """
    matches = list(BREAKERS_RE.finditer(left_context))
    if not matches:
        return left_context
    last = matches[-1]
    return left_context[last.end():].strip()


def _best_trigger_pos(left_context: str, patterns: List[Pattern]) -> Optional[int]:
    """
    Return the position (end index) of the closest trigger match to entity
    within left_context, or None.
    """
    best = None
    for pat in patterns:
        for m in pat.finditer(left_context):
            # We care about closeness to entity => later match is closer
            pos = m.end()
            if best is None or pos > best:
                best = pos
    return best


# ----------------------------
# Smoke tests (quick sanity)
# ----------------------------

if __name__ == "__main__":
    def run(sentence: str, span: str, ent_type: str):
        s_lc = sentence
        start = s_lc.lower().find(span.lower())
        end = start + len(span)
        out = classify_assertion(sentence, start, end, ent_type)
        print(f"[{out:10}] {ent_type:10} | {span!r} | {sentence}")

    # 1) “sem ... porém refere ...” => second entity should be PRESENT
    run("sem perda de consciência, porém refere cefaleia intensa", "cefaleia", "SYMPTOM")

    # 2) "sem crepitações" => crepitações NEGATED; tórax ANATOMY PRESENT
    run("tórax indolor à palpação; sem crepitações", "crepitações", "SYMPTOM")
    run("tórax indolor à palpação; sem crepitações", "tórax", "ANATOMY")

    # 3) "nega vômitos" => NEGATED
    run("nega vômitos", "vômitos", "SYMPTOM")

    # 4) possible
    run("suspeita de pneumonia", "pneumonia", "PROBLEM")

    # 5) historical
    run("HPP: diabetes mellitus tipo 2", "diabetes", "PROBLEM")
