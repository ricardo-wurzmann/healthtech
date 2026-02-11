"""
Canonical Vocabulary Loader for NER
Loads entries from canonical_v1_1 and provides matching capabilities.
"""
import pandas as pd
from pathlib import Path
from typing import List, Dict, Optional, Set
import re


def normalize_drug_name(name: str) -> str:
    """
    Normalize drug name for flexible matching.
    
    Examples:
    "PARACETAMOL 500MG COMPRIMIDO" → "paracetamol"
    "OMEPRAZOL 20MG CAPSULA" → "omeprazol"
    "METFORMINA CLORIDRATO 850MG" → "metformina"
    """
    # Convert to lowercase
    normalized = name.lower()
    
    # Remove dosage patterns (500mg, 20mg, etc)
    normalized = re.sub(r'\d+\s*(mg|g|ml|mcg|ui)', '', normalized)
    
    # Remove form patterns (comprimido, capsula, etc)
    form_words = r'(comprimido|capsula|solucao|ampola|frasco|suspensao|creme|pomada|dragea|xarope|solução|cápsula|drágea)'
    normalized = re.sub(form_words, '', normalized)
    
    # Remove common stopwords and connectors
    stopwords = {'de', 'da', 'do', 'com', 'em', 'a', 'o', 'e', 'para', 'por'}
    words = normalized.split()
    words = [w for w in words if w not in stopwords]
    
    # Get first word (active ingredient)
    if not words:
        return ""
    
    first_word = words[0]
    
    # Require minimum 4 characters (filters out short ambiguous words)
    if len(first_word) < 4:
        return ""
    
    return first_word.strip()


class CanonicalLexiconLoader:
    """
    Loads canonical vocabulary entries and provides exact matching.
    Does NOT modify existing baseline_ner.py - this is parallel implementation.
    """
    
    # Portuguese stopwords that should not be matched as medical terms
    PORTUGUESE_STOPWORDS = {
        # Prepositions and articles (lowercase)
        'a', 'o', 'e', 'de', 'da', 'do', 'em', 'na', 'no', 'para', 'por',
        'com', 'sem', 'sob', 'sobre', 'ou', 'mas', 'se', 'ao', 'aos',
        # Medical context words that shouldn't be abbreviations
        'as', 'os', 'um', 'uma', 'uns', 'umas', 'que', 'qual'
    }
    
    def __init__(self, canonical_version="v1_1"):
        """
        Initialize loader with specific canonical version.
        
        Args:
            canonical_version: Version string (e.g., "v1_1" for canonical_v1_1)
        """
        self.version = canonical_version
        self.base_dir = Path(__file__).parent.parent / "data" / "vocab"
        self.canonical_dir = self.base_dir / f"canonical_{canonical_version}"
        
        # Loaded data
        self.concepts_df = None
        self.entries_df = None
        self.blocked_terms = set()
        self.ambiguous_terms = set()
        
        # Indexes for fast lookup
        self.entry_index = {}  # {entry_text: [list of entry records]}
        self.concept_index = {}  # {concept_id: concept record}
        self.drug_index = {}  # {normalized_drug_name: [list of concept_ids]}
        
    def load(self):
        """Load all canonical files and build indexes."""
        print(f"Loading canonical {self.version}...")
        
        # Load CSVs
        self.concepts_df = pd.read_csv(self.canonical_dir / "concepts.csv")
        self.entries_df = pd.read_csv(self.canonical_dir / "entries.csv")
        
        # Load blocked terms
        blocked_df = pd.read_csv(self.canonical_dir / "blocked_terms.csv")
        if len(blocked_df) > 0:
            self.blocked_terms = set(blocked_df['term'].str.upper())
        
        # Load ambiguous terms
        ambig_df = pd.read_csv(self.canonical_dir / "ambiguity.csv")
        if len(ambig_df) > 0:
            self.ambiguous_terms = set(ambig_df['entry_text'].str.upper())
        
        # Build indexes
        self._build_indexes()
        
        print(f"Loaded {len(self.concepts_df)} concepts")
        print(f"Loaded {len(self.entries_df)} entries")
        print(f"{len(self.blocked_terms)} blocked terms")
        print(f"{len(self.ambiguous_terms)} ambiguous terms")
        
    def _build_indexes(self):
        """Build lookup indexes for fast matching."""
        # Concept index
        for _, row in self.concepts_df.iterrows():
            self.concept_index[row['concept_id']] = row.to_dict()
        
        # Entry index (normalized to uppercase for case-insensitive matching)
        for _, row in self.entries_df.iterrows():
            # Skip if entry_text is not a string (e.g., NaN)
            if not isinstance(row['entry_text'], str):
                continue
            
            entry_text = row['entry_text'].upper()
            
            # Skip blocked entries
            if row['match_policy'] == 'blocked':
                continue
                
            if entry_text not in self.entry_index:
                self.entry_index[entry_text] = []
            
            self.entry_index[entry_text].append(row.to_dict())
        
        # Build drug-specific index for flexible matching
        drug_concepts = self.concepts_df[self.concepts_df['entity_type'] == 'DRUG']
        for _, concept in drug_concepts.iterrows():
            normalized = normalize_drug_name(concept['concept_name'])
            if normalized:
                if normalized not in self.drug_index:
                    self.drug_index[normalized] = []
                self.drug_index[normalized].append(concept['concept_id'])
        
        print(f"Built drug index with {len(self.drug_index)} normalized names")
    
    def should_skip_match(self, entry_text: str, entry: Dict, original_text: str = None) -> bool:
        """
        Determine if an entry should be skipped.
        
        Args:
            entry_text: The normalized (uppercase) entry text
            entry: The entry dictionary
            original_text: The original text from document (for case checking)
        
        Returns:
            True if match should be skipped
        """
        length = len(entry_text)
        
        # Always allow codes regardless of length
        if entry['entry_type'] == 'code':
            return False
        
        # Skip 1-letter entries (too ambiguous)
        if length == 1:
            return True
        
        # Check if it's a stopword (case-insensitive check)
        if entry_text.lower() in self.PORTUGUESE_STOPWORDS:
            return True
        
        # For 2-letter entries
        if length == 2:
            # Allow if it's marked as abbreviation in vocabulary
            if entry['entry_type'] == 'abbr':
                # BUT require it to be uppercase in original text
                # This filters "em" (lowercase) but keeps "EM" (uppercase)
                if original_text and original_text.isupper():
                    return False
                else:
                    return True
            # Skip other 2-letter entries
            return True
        
        return False
    
    def match_text(self, text: str, entity_types: Optional[List[str]] = None) -> List[Dict]:
        """
        Find exact matches in text.
        
        Args:
            text: Input text to search
            entity_types: Filter by entity types (e.g., ['PROBLEM', 'DRUG'])
        
        Returns:
            List of match dictionaries with:
            {
                "text": matched text,
                "concept_id": concept ID,
                "entity_type": PROBLEM/PROCEDURE/DRUG/TEST/ABBREV,
                "vocabulary": CID10/TUSS_PROC/etc,
                "match_type": "exact",
                "match_policy": safe_exact/context_required,
                "confidence": 0.0-1.0,
                "start": char position,
                "end": char position
            }
        """
        matches = []
        text_upper = text.upper()
        
        # Find all matches with word boundary detection
        for entry_text, entry_records in self.entry_index.items():
            # Add word boundaries to prevent substring matches
            pattern = r'\b' + re.escape(entry_text) + r'\b'
            
            # Find all occurrences of this entry in the text
            for match in re.finditer(pattern, text_upper):
                start, end = match.span()
                original_matched_text = text[start:end]  # Get original case
                
                # For each entry record (could be multiple concepts for same text)
                for entry in entry_records:
                    # Check if we should skip this match (with original text for case checking)
                    if self.should_skip_match(entry_text, entry, original_matched_text):
                        continue
                    
                    concept = self.concept_index.get(entry['concept_id'])
                    
                    if not concept:
                        continue
                    
                    # Filter by entity type if specified
                    if entity_types and concept['entity_type'] not in entity_types:
                        continue
                    
                    # Build match result
                    match_result = {
                        "text": text[start:end],
                        "concept_id": concept['concept_id'],
                        "concept_name": concept['concept_name'],
                        "entity_type": concept['entity_type'],
                        "vocabulary": concept['vocabulary'],
                        "match_type": "exact",
                        "match_policy": entry['match_policy'],
                        "entry_type": entry['entry_type'],
                        "confidence": self._calculate_confidence(entry),
                        "start": start,
                        "end": end
                    }
                    
                    matches.append(match_result)
        
        # Add drug-specific matching with normalization
        if entity_types is None or 'DRUG' in entity_types:
            drug_matches = self._match_drugs(text)
            matches.extend(drug_matches)
        
        # Sort by position and remove overlaps
        matches.sort(key=lambda x: x['start'])
        matches = self._remove_overlapping_matches(matches)
        
        return matches
    
    def _match_drugs(self, text: str) -> List[Dict]:
        """
        Match drug names with flexible normalization.
        
        Looks for drug names in text and matches against normalized TUSS_DRUG entries.
        """
        drug_matches = []
        text_lower = text.lower()
        
        # For each normalized drug name
        for normalized_name, concept_ids in self.drug_index.items():
            # Skip if normalized name is too short or empty
            if not normalized_name or len(normalized_name) < 4:
                continue
            
            # Skip if it's a Portuguese stopword
            if normalized_name in self.PORTUGUESE_STOPWORDS:
                continue
            
            # Look for exact drug name or with optional dosage
            # Matches: "paracetamol", "paracetamol 500mg"
            # Does NOT match: "paracetamolzinho", "completar"
            pattern = r'\b' + re.escape(normalized_name) + r'(?:\s+\d+\s*(?:mg|g|ml|mcg|ui))?\b'
            
            for match in re.finditer(pattern, text_lower):
                start, end = match.span()
                matched_text = text[start:end]
                
                # For each concept that matches this normalized name
                for concept_id in concept_ids:
                    concept = self.concept_index.get(concept_id)
                    if not concept:
                        continue
                    
                    drug_matches.append({
                        "text": matched_text,
                        "concept_id": concept['concept_id'],
                        "concept_name": concept['concept_name'],
                        "entity_type": "DRUG",
                        "vocabulary": "TUSS_DRUG",
                        "match_type": "normalized",
                        "match_policy": "safe_exact",
                        "entry_type": "drug_normalized",
                        "confidence": 0.85,  # Slightly lower confidence for normalized
                        "start": start,
                        "end": end
                    })
        
        return drug_matches
    
    def _remove_overlapping_matches(self, matches: List[Dict]) -> List[Dict]:
        """
        Remove overlapping matches, keeping higher confidence ones.
        """
        if not matches:
            return matches
        
        # Sort by start position, then by confidence (descending)
        matches.sort(key=lambda x: (x['start'], -x['confidence']))
        
        filtered = []
        last_end = -1
        
        for match in matches:
            # If this match doesn't overlap with previous, keep it
            if match['start'] >= last_end:
                filtered.append(match)
                last_end = match['end']
        
        return filtered
    
    def _calculate_confidence(self, entry: Dict) -> float:
        """
        Calculate confidence score for a match.
        
        Rules:
        - official names: 0.95
        - codes: 0.90
        - abbreviations (non-ambiguous): 0.85
        - abbreviations (ambiguous): 0.50 (needs context)
        """
        if entry['match_policy'] == 'context_required':
            return 0.50
        
        if entry['entry_type'] == 'official':
            return 0.95
        elif entry['entry_type'] == 'code':
            return 0.90
        elif entry['entry_type'] == 'abbr':
            return 0.85
        else:
            return 0.80
    
    def get_concept(self, concept_id: str) -> Optional[Dict]:
        """Get full concept details by ID."""
        return self.concept_index.get(concept_id)
    
    def get_stats(self) -> Dict:
        """Get loader statistics."""
        return {
            "version": self.version,
            "total_concepts": len(self.concepts_df),
            "total_entries": len(self.entries_df),
            "indexed_entries": len(self.entry_index),
            "blocked_terms": len(self.blocked_terms),
            "ambiguous_terms": len(self.ambiguous_terms),
            "by_vocabulary": self.concepts_df['vocabulary'].value_counts().to_dict(),
            "by_entity_type": self.concepts_df['entity_type'].value_counts().to_dict()
        }


if __name__ == "__main__":
    # Test the loader
    loader = CanonicalLexiconLoader()
    loader.load()
    
    print("\n" + "="*60)
    print("LOADER STATISTICS")
    print("="*60)
    stats = loader.get_stats()
    for key, value in stats.items():
        print(f"{key}: {value}")
    
    # Test matching on sample text
    test_text = "Paciente com diarreia (A09). Consulta em consultorio."
    print("\n" + "="*60)
    print(f"TEST MATCHING: {test_text}")
    print("="*60)
    matches = loader.match_text(test_text)
    print(f"\nFound {len(matches)} matches:")
    for match in matches:
        print(f"  - '{match['text']}' [{match['entity_type']}] "
              f"concept_id={match['concept_id']}, conf={match['confidence']:.2f}")
