from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import json


# Label normalization map (handles synonyms/variants)
LABEL_MAP = {
    # Normalize common variants
    "DIAGNOSIS": "PROBLEM",
    "DISEASE": "PROBLEM",
    "CONDITION": "PROBLEM",
    "SIGN": "SYMPTOM",
    "SYMPTOM": "SYMPTOM",
    "TEST": "TEST",
    "EXAM": "TEST",
    "EXAMINATION": "TEST",
    "DRUG": "DRUG",
    "MEDICATION": "DRUG",
    "MEDICINE": "DRUG",
    "PROCEDURE": "PROCEDURE",
    "ANATOMY": "ANATOMY",
    "BODY_PART": "ANATOMY",
}


def normalize_label(label: str) -> str:
    """
    Normalize entity type labels to a canonical form.
    
    Args:
        label: Entity type label (case-insensitive)
    
    Returns:
        Normalized label (uppercase)
    """
    if not label:
        return ""
    label_upper = label.upper().strip()
    return LABEL_MAP.get(label_upper, label_upper)


@dataclass
class GoldEntity:
    """Gold standard entity annotation."""
    start: int
    end: int
    text: str
    type: str
    assertion: Optional[str] = None
    notes: Optional[str] = None
    
    def __post_init__(self):
        """Normalize label after initialization."""
        self.type = normalize_label(self.type)
        if self.assertion:
            self.assertion = self.assertion.upper().strip()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        d = {
            "start": self.start,
            "end": self.end,
            "text": self.text,
            "type": self.type,
        }
        if self.assertion:
            d["assertion"] = self.assertion
        if self.notes:
            d["notes"] = self.notes
        return d
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> GoldEntity:
        """Create from dictionary."""
        return cls(
            start=d["start"],
            end=d["end"],
            text=d["text"],
            type=d["type"],
            assertion=d.get("assertion"),
            notes=d.get("notes"),
        )


@dataclass
class GoldCase:
    """Gold standard case annotation."""
    case_id: str | int
    group: Optional[str] = None
    raw_text: str = ""
    gold_entities: List[GoldEntity] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSONL output."""
        d = {
            "case_id": self.case_id,
            "raw_text": self.raw_text,
            "gold_entities": [e.to_dict() for e in self.gold_entities],
        }
        if self.group:
            d["group"] = self.group
        if self.metadata:
            d["metadata"] = self.metadata
        return d
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> GoldCase:
        """Create from dictionary (JSONL input)."""
        return cls(
            case_id=d["case_id"],
            group=d.get("group"),
            raw_text=d.get("raw_text", ""),
            gold_entities=[GoldEntity.from_dict(e) for e in d.get("gold_entities", [])],
            metadata=d.get("metadata", {}),
        )


@dataclass
class PredEntity:
    """Predicted entity from pipeline output."""
    start: int
    end: int
    span: str  # or "text" field
    type: str
    score: float = 0.0
    assertion: Optional[str] = None
    evidence: Optional[str] = None
    
    def __post_init__(self):
        """Normalize label after initialization."""
        self.type = normalize_label(self.type)
        if self.assertion:
            self.assertion = self.assertion.upper().strip()
    
    @property
    def text(self) -> str:
        """Alias for span for compatibility."""
        return self.span
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> PredEntity:
        """Create from pipeline output dictionary."""
        # Handle both "span" and "text" fields
        text = d.get("span") or d.get("text", "")
        return cls(
            start=d["start"],
            end=d["end"],
            span=text,
            type=d["type"],
            score=d.get("score", 0.0),
            assertion=d.get("assertion"),
            evidence=d.get("evidence"),
        )


@dataclass
class PredCase:
    """Predicted case from pipeline output."""
    case_id: str | int
    doc_id: Optional[str] = None
    text: Optional[str] = None  # normalized_text or raw_text
    raw_text: Optional[str] = None
    entities: List[PredEntity] = field(default_factory=list)
    sentences: Optional[List[Dict[str, Any]]] = None
    group: Optional[str] = None
    
    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> PredCase:
        """Create from pipeline output dictionary."""
        # Get text - prefer text, fallback to raw_text
        text = d.get("text") or d.get("raw_text") or d.get("normalized_text", "")
        raw_text = d.get("raw_text") or text
        
        return cls(
            case_id=d.get("case_id") or d.get("doc_id", ""),
            doc_id=d.get("doc_id"),
            text=text,
            raw_text=raw_text,
            entities=[PredEntity.from_dict(e) for e in d.get("entities", [])],
            sentences=d.get("sentences"),
            group=d.get("group"),
        )
    
    def get_text_for_evaluation(self) -> str:
        """Get the text that should be used for evaluation (with offsets)."""
        # Use text if available (normalized), otherwise raw_text
        return self.text or self.raw_text or ""

