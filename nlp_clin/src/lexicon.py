from __future__ import annotations
from pathlib import Path
from typing import List, Tuple, Set

try:
    from unidecode import unidecode
except ImportError:
    # Fallback if unidecode not available
    def unidecode(s: str) -> str:
        return s.encode('ascii', 'ignore').decode('ascii')

# Lexicon file mappings: (filename, entity_type, priority)
# Priority: lower number = higher priority (loaded first)
LEXICON_FILES = [
    ("symptoms_core_ptbr.txt", "SYMPTOM", 1),  # Core symptoms have highest priority
    ("symptoms_expanded_ptbr.txt", "SYMPTOM", 2),  # Expanded symptoms (fallback)
    ("anatomy_ptbr.txt", "ANATOMY", 1),
    ("procedures_ptbr.txt", "PROCEDURE", 1),
    ("tests_exams_ptbr.txt", "TEST", 1),
    ("drugs_ptbr.txt", "DRUG", 1),
]


def load_lexicon_file(filepath: Path, entity_type: str) -> List[Tuple[str, str]]:
    """
    Load a lexicon file and return list of (term, entity_type) tuples.
    
    Args:
        filepath: Path to the lexicon file
        entity_type: Entity type to assign to all terms in this file
    
    Returns:
        List of (term, entity_type) tuples
    """
    if not filepath.exists():
        raise FileNotFoundError(f"Lexicon file not found: {filepath}")
    
    entries = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            term = line.strip()
            if term:  # Skip empty lines
                entries.append((term, entity_type))
    
    return entries


def load_all_lexicons(lexicon_dir: Path | str = None) -> List[Tuple[str, str]]:
    """
    Load all lexicon files with priority handling.
    
    For symptoms: core symptoms are loaded first, then expanded.
    If a term appears in both, the core version (higher priority) is kept.
    
    Args:
        lexicon_dir: Directory containing lexicon files. 
                     Defaults to data/lexicons relative to this file.
    
    Returns:
        List of (term, entity_type) tuples with duplicates removed (keeping first/higher priority)
    """
    if lexicon_dir is None:
        # Get directory relative to this file
        this_file = Path(__file__)
        lexicon_dir = this_file.parent.parent / "data" / "lexicons"
    else:
        lexicon_dir = Path(lexicon_dir)
    
    if not lexicon_dir.exists():
        raise FileNotFoundError(f"Lexicon directory not found: {lexicon_dir}")
    
    # Load lexicons in priority order
    all_entries: List[Tuple[str, str]] = []
    seen_terms: Set[str] = set()  # Track normalized terms to avoid duplicates
    
    # Sort by priority (lower number = higher priority)
    sorted_files = sorted(LEXICON_FILES, key=lambda x: x[2])
    
    for filename, entity_type, priority in sorted_files:
        filepath = lexicon_dir / filename
        if not filepath.exists():
            print(f"Warning: Lexicon file not found: {filepath}")
            continue
        
        entries = load_lexicon_file(filepath, entity_type)
        
        # Add entries, skipping duplicates (keep first/higher priority)
        for term, etype in entries:
            # Normalize term for duplicate detection (case-insensitive, no accents)
            normalized = unidecode(term.lower().strip())
            
            if normalized not in seen_terms:
                seen_terms.add(normalized)
                all_entries.append((term, etype))
    
    return all_entries


# Load lexicons on module import
# Fallback to hardcoded list if files not found
try:
    LEXICON = load_all_lexicons()
    print(f"Loaded {len(LEXICON)} lexicon entries from files")
except Exception as e:
    print(f"Warning: Failed to load lexicon files: {e}")
    print("Falling back to hardcoded lexicon")
    # Fallback to original hardcoded list
    LEXICON = [
        # sintomas
        ("vômito", "SYMPTOM"),
        ("vômitos", "SYMPTOM"),
        ("náusea", "SYMPTOM"),
        ("dor epigástrica", "SYMPTOM"),
        ("dor abdominal", "SYMPTOM"),
        ("febre", "SYMPTOM"),
        ("disúria", "SYMPTOM"),
        ("cefaleia", "SYMPTOM"),
        # exames / procedimentos
        ("fast", "PROCEDURE"),  # trauma FAST
        ("cultura de urina", "TEST"),
        ("hemograma", "TEST"),
        ("rx", "TEST"),
        ("raio x", "TEST"),
        ("tomografia", "TEST"),
        # drogas
        ("cefadroxila", "DRUG"),
        ("dipirona", "DRUG"),
        ("paracetamol", "DRUG"),
    ]
