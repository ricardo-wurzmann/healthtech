from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any, Optional
import json


@dataclass
class Document:
    doc_id: str
    text: str
    source_path: str
    case_id: int
    group: str


def _reconstruct_text_from_structured(case: Dict[str, Any]) -> Optional[str]:
    """Fallback: reconstruct text from structured fields if raw_text is missing."""
    parts = []
    if case.get("qd"):
        parts.append(f"QD: {case['qd']}")
    if case.get("hpma"):
        parts.append(f"HPMA: {case['hpma']}")
    if case.get("isda"):
        parts.append(f"ISDA: {case['isda']}")
    if case.get("ap"):
        parts.append(f"AP: {case['ap']}")
    if case.get("af"):
        parts.append(f"AF: {case['af']}")
    return " ".join(parts) if parts else None


def load_json_cases(json_path: str | Path) -> List[Document]:
    """
    Load cases from JSON file and return list of Document objects.
    
    Each case should have:
    - case_id (int)
    - group (str, e.g., "prontuario" or "caso_estruturado")
    - raw_text (str) - primary text source
    - Optional structured fields: id, qd, hpma, isda, ap, af
    
    Returns documents with doc_id = {stem}_case_{case_id:04d}
    """
    json_path = Path(json_path)
    data = json.loads(json_path.read_text(encoding="utf-8"))
    
    if not isinstance(data, list):
        raise ValueError(f"Expected JSON array, got {type(data)}")
    
    stem = json_path.stem
    documents = []
    
    for case in data:
        case_id = case.get("case_id")
        if case_id is None:
            raise ValueError("Missing 'case_id' in case")
        
        group = case.get("group", "unknown")
        
        # Get text: prefer raw_text, fallback to structured fields
        text = case.get("raw_text")
        if not text:
            text = _reconstruct_text_from_structured(case)
            if not text:
                raise ValueError(f"Case {case_id}: no text available (missing raw_text and structured fields)")
        
        doc_id = f"{stem}_case_{case_id:04d}"
        
        documents.append(Document(
            doc_id=doc_id,
            text=text,
            source_path=str(json_path),
            case_id=case_id,
            group=group,
        ))
    
    return documents

