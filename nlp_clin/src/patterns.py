from __future__ import annotations

import re
from typing import List, Tuple


PATTERN_DEFS: List[Tuple[re.Pattern, str, float]] = [
    # Glasgow Coma Scale / GCS
    (
        re.compile(r"\b(?:GCS|Glasgow|ECG)\s*(?:=|:)?\s*(?:[3-9]|1[0-5])\b", re.IGNORECASE),
        "TEST",
        0.98,
    ),
    # Blood pressure (PA 120x70, 120/70, 120 x 70)
    (
        re.compile(r"\b(?:PA\s*)?\d{2,3}\s*(?:x|/)\s*\d{2,3}\b", re.IGNORECASE),
        "TEST",
        0.97,
    ),
    # Heart rate (FC 86, pulso 112 bpm)
    (
        re.compile(
            r"\b(?:FC|frequ[eê]ncia\s*card[ií]aca|pulso)\s*[:=]?\s*\d{2,3}\s*(?:bpm)?\b",
            re.IGNORECASE,
        ),
        "TEST",
        0.97,
    ),
    # Respiratory rate (FR 16 irpm)
    (
        re.compile(
            r"\b(?:FR|frequ[eê]ncia\s*respirat[óo]ria)\s*[:=]?\s*\d{1,3}\s*(?:irpm|rpm|ipm)?\b",
            re.IGNORECASE,
        ),
        "TEST",
        0.97,
    ),
    # Oxygen saturation (sat 98%, saturação 97%)
    (
        re.compile(r"\b(?:sat|saturação|saturacao|SpO2)\s*[:=]?\s*\d{2,3}\s*%?\b", re.IGNORECASE),
        "TEST",
        0.97,
    ),
    # FAST procedure
    (
        re.compile(r"\bFAST\b", re.IGNORECASE),
        "PROCEDURE",
        0.95,
    ),
]
