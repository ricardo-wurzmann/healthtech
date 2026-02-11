"""
Canonical vocabulary-based NER (parallel to baseline_ner.py)
Uses canonical_v1_1 instead of lexicons/*.txt
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple
import sys

# Add scripts to path to import CanonicalLexiconLoader
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from ner_canonical_loader import CanonicalLexiconLoader


@dataclass
class EntitySpan:
    """Entity span (same structure as baseline_ner.EntitySpan for compatibility)."""
    span: str
    start: int
    end: int
    type: str
    score: float
    sentence_start: int
    sentence_end: int
    evidence: str | dict


# Global loader instance (loaded once, singleton pattern)
_CANONICAL_LOADER = None


def get_canonical_loader():
    """Lazy load canonical vocabulary (singleton pattern)."""
    global _CANONICAL_LOADER
    if _CANONICAL_LOADER is None:
        print("[CANONICAL NER] Loading canonical vocabulary v1.1...")
        _CANONICAL_LOADER = CanonicalLexiconLoader(canonical_version="v1_1")
        _CANONICAL_LOADER.load()
        stats = _CANONICAL_LOADER.get_stats()
        print(f"[CANONICAL NER] Loaded {stats['total_concepts']} concepts, {stats['total_entries']} entries")
    return _CANONICAL_LOADER


def extract_entities_canonical(
    text: str,
    sentences: List[Tuple[str, int, int]],
    entity_types: List[str] = None
) -> List[EntitySpan]:
    """
    Extract entities using canonical vocabulary.
    
    Args:
        text: Full document text
        sentences: List of (sentence_text, start, end) tuples
        entity_types: Optional filter (e.g., ['PROBLEM', 'DRUG'])
    
    Returns:
        List of EntitySpan objects (same format as baseline_ner)
    """
    loader = get_canonical_loader()
    
    # Match entities in full text
    matches = loader.match_text(text, entity_types=entity_types)
    
    # Convert to EntitySpan format (matching baseline_ner output)
    entity_spans = []
    
    for match in matches:
        # Find which sentence this entity belongs to
        sentence_start = 0
        sentence_end = len(text)
        sentence_text = text
        
        for sent_text, s_start, s_end in sentences:
            if s_start <= match['start'] < s_end:
                sentence_start = s_start
                sentence_end = s_end
                sentence_text = sent_text
                break
        
        # Create evidence dict with canonical metadata
        evidence = {
            'concept_id': match['concept_id'],
            'concept_name': match['concept_name'],
            'vocabulary': match['vocabulary'],
            'match_type': match['match_type'],
            'match_policy': match['match_policy'],
            'entry_type': match['entry_type'],
            'sentence': sentence_text.strip()
        }
        
        # Create EntitySpan (same schema as baseline)
        entity_span = EntitySpan(
            span=match['text'],
            start=match['start'],
            end=match['end'],
            type=match['entity_type'],
            score=match['confidence'],
            sentence_start=sentence_start,
            sentence_end=sentence_end,
            evidence=evidence
        )
        
        entity_spans.append(entity_span)
    
    # Sort by position (same as baseline)
    return sorted(entity_spans, key=lambda x: (x.start, -x.score))
