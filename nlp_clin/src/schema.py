from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional

@dataclass
class LinkCandidate:
    system: str
    code: str
    label: str
    score: float

@dataclass
class EntityOut:
    span: str
    start: int
    end: int
    type: str
    score: float
    assertion: str
    evidence: str
    links: List[LinkCandidate]
    icd10: List[Dict[str, Any]]  # deixa flexível no MVP

@dataclass
class DocOut:
    doc_id: str
    source: str
    text: str
    entities: List[EntityOut]
    case_id: int
    group: str
