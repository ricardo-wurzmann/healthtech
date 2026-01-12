"""
Entity filtering module for removing junk predictions.

Filters out invalid entity spans based on length, stopwords, and clinical nucleus constraints.
"""
from __future__ import annotations
import re
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Set
from unidecode import unidecode


# Portuguese stopwords (common function words)
DEFAULT_STOPWORDS = {
    "a", "o", "os", "as", "de", "da", "do", "das", "dos", "e", "em", "no", "na", 
    "nos", "nas", "com", "sem", "por", "para", "ao", "aos", "à", "às", "um", "uma", 
    "uns", "umas", "que", "se", "foi", "está", "esta", "relatando", "refere", 
    "nega", "apresenta", "paciente", "ao", "aos", "pela", "pelo", "pelas", "pelos",
    "em", "na", "no", "nas", "nos", "da", "do", "das", "dos"
}

# Clinical symptom nucleus tokens (must be present in SYMPTOM spans)
DEFAULT_SYMPTOM_NUCLEUS = {
    "dor", "cefaleia", "febre", "vomito", "vômito", "náusea", "nausea", "dispneia",
    "tosse", "diarreia", "disúria", "disuria", "prostração", "astenia", "tontura",
    "sangramento", "prurido", "edema", "cansaço", "fadiga", "palpitação", "palpitacao",
    "mal", "estar", "desconforto", "ardor", "queimação", "queimacao", "ardência",
    "ardencia", "formigamento", "parestesia", "anorexia", "perda", "ganho", "peso",
    "sede", "poliúria", "poliuria", "oligúria", "oliguria", "incontinência", "incontinencia",
    "constipação", "constipacao", "obstipação", "obstipacao", "flatulência", "flatulencia",
    "hemorragia", "hematúria", "hematuria", "melena", "hematêmese", "hematemese",
    "hemoptise", "hemoptise", "epistaxe", "síncope", "sincope", "convulsão", "convulsao",
    "tremor", "rigidez", "espasmo", "câimbra", "caimbra", "cramp", "fraqueza", "debilidade",
    "mialgia", "artralgia", "cervicalgia", "lombalgia", "dorsalgia", "cefaleia", "cefalgia"
}


@dataclass
class FilterConfig:
    """Configuration for entity filtering."""
    min_chars: int = 4
    apply_to_types: Set[str] = None  # If None, applies to all types
    stopwords: Set[str] = None
    symptom_nucleus: Set[str] = None
    trim_punct: bool = True
    
    def __post_init__(self):
        """Set defaults if None."""
        if self.apply_to_types is None:
            self.apply_to_types = {"SYMPTOM"}  # Default: only filter SYMPTOM
        if self.stopwords is None:
            self.stopwords = DEFAULT_STOPWORDS.copy()
        if self.symptom_nucleus is None:
            self.symptom_nucleus = DEFAULT_SYMPTOM_NUCLEUS.copy()


def normalize_token(token: str) -> str:
    """Normalize token for matching (lowercase, remove accents)."""
    return unidecode(token.lower().strip())


def tokenize_span(span: str) -> List[str]:
    """Tokenize span by whitespace and punctuation boundaries."""
    # Split on whitespace and punctuation, keep tokens
    tokens = re.findall(r'\b\w+\b', span.lower())
    return tokens


def trim_punctuation(text: str, start: int, end: int) -> tuple[int, int]:
    """
    Trim leading/trailing punctuation from span and adjust offsets.
    
    Returns:
        (new_start, new_end) with adjusted offsets
    """
    if start >= end or start < 0 or end > len(text):
        return start, end
    
    span_text = text[start:end]
    
    # Trim leading punctuation
    new_start = start
    while new_start < end and not text[new_start].isalnum() and not text[new_start].isspace():
        new_start += 1
    
    # Trim trailing punctuation
    new_end = end
    while new_end > new_start and not text[new_end - 1].isalnum() and not text[new_end - 1].isspace():
        new_end -= 1
    
    return new_start, new_end


def filter_entities(
    entities: List[Dict[str, Any]], 
    raw_text: str, 
    config: Optional[FilterConfig] = None
) -> List[Dict[str, Any]]:
    """
    Filter entities to remove junk predictions.
    
    Args:
        entities: List of entity dictionaries with at least: span, start, end, type
        raw_text: Original text (for offset validation and trimming)
        config: FilterConfig (uses defaults if None)
    
    Returns:
        Filtered list of entities
    """
    if config is None:
        config = FilterConfig()
    
    filtered = []
    
    for ent in entities:
        # Get entity fields (handle both "span" and "text" keys)
        span_text = ent.get("span") or ent.get("text", "")
        start = ent.get("start")
        end = ent.get("end")
        entity_type = ent.get("type", "")
        
        # Rule 1: Span integrity
        if not isinstance(start, int) or not isinstance(end, int):
            continue  # Skip entities without valid offsets
        
        if start < 0 or end > len(raw_text) or end <= start:
            continue  # Invalid offsets
        
        # Extract span from text
        extracted_span = raw_text[start:end].strip()
        if not extracted_span:
            continue  # Empty span
        
        # Rule 2: Minimum length
        if len(extracted_span) < config.min_chars:
            continue
        
        # Check if span has at least one alphabetic character
        if not any(c.isalpha() for c in extracted_span):
            continue  # Only punctuation/numbers
        
        # Rule 3: Trim punctuation (optional)
        if config.trim_punct:
            new_start, new_end = trim_punctuation(raw_text, start, end)
            if new_start < new_end:
                # Update entity with trimmed offsets
                ent = ent.copy()
                ent["start"] = new_start
                ent["end"] = new_end
                ent["span"] = raw_text[new_start:new_end]
                extracted_span = raw_text[new_start:new_end]
                start, end = new_start, new_end
        
        # Check if filtering applies to this entity type
        if config.apply_to_types and entity_type not in config.apply_to_types:
            # Not filtered, keep as-is
            filtered.append(ent)
            continue
        
        # Rule 4: Stopword-only spans
        tokens = tokenize_span(extracted_span)
        if not tokens:
            continue  # No tokens found
        
        # Check if all tokens are stopwords
        normalized_stopwords = {normalize_token(sw) for sw in config.stopwords}
        normalized_tokens = {normalize_token(t) for t in tokens}
        
        if normalized_tokens.issubset(normalized_stopwords):
            continue  # All tokens are stopwords
        
        # Rule 5: SYMPTOM nucleus constraint
        if entity_type == "SYMPTOM":
            normalized_nucleus = {normalize_token(n) for n in config.symptom_nucleus}
            
            # Check if any token is in nucleus set
            has_nucleus = any(normalize_token(t) in normalized_nucleus for t in tokens)
            
            if not has_nucleus:
                continue  # No nucleus token found
        
        # Entity passed all filters
        filtered.append(ent)
    
    return filtered


