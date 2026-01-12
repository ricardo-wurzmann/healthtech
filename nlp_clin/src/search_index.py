from __future__ import annotations
from dataclasses import dataclass
from typing import List, Tuple, Set, Dict
import re
from unidecode import unidecode


@dataclass
class LexiconEntry:
    """Normalized lexicon entry with tokens."""
    original_term: str
    normalized_term: str
    tokens: List[str]
    entity_type: str


@dataclass
class MatchCandidate:
    """Candidate span match from lexicon."""
    term: str
    entity_type: str
    normalized_term: str
    tokens: List[str]
    match_type: str  # "exact", "token", "fuzzy"


class LexiconIndex:
    """
    Normalized token-based index for fast lexicon matching.
    
    Strategy:
    1. Normalize terms: lowercase, remove accents, collapse whitespace, strip punctuation (keep hyphens)
    2. Tokenize into words
    3. Build index for fast candidate generation
    4. Support exact phrase matches, token-based matching, and fuzzy fallback
    """
    
    def __init__(self, lexicon: List[Tuple[str, str]]):
        """
        Initialize index from lexicon.
        
        Args:
            lexicon: List of (term, entity_type) tuples
        """
        self.entries: List[LexiconEntry] = []
        self.token_to_entries: Dict[str, List[int]] = {}  # token -> list of entry indices
        self.single_token_entries: List[LexiconEntry] = []
        self.multi_token_entries: List[LexiconEntry] = []
        
        for term, entity_type in lexicon:
            normalized = self._normalize(term)
            tokens = self._tokenize(normalized)
            
            entry = LexiconEntry(
                original_term=term,
                normalized_term=normalized,
                tokens=tokens,
                entity_type=entity_type,
            )
            
            idx = len(self.entries)
            self.entries.append(entry)
            
            # Index by tokens
            for token in tokens:
                if token not in self.token_to_entries:
                    self.token_to_entries[token] = []
                self.token_to_entries[token].append(idx)
            
            # Separate single vs multi-token
            if len(tokens) == 1:
                self.single_token_entries.append(entry)
            else:
                self.multi_token_entries.append(entry)
    
    @staticmethod
    def _normalize(text: str) -> str:
        """
        Normalize text for matching:
        - Lowercase
        - Remove accents
        - Collapse whitespace
        - Strip punctuation (but keep hyphens)
        """
        # Remove accents
        text = unidecode(text.lower())
        # Collapse whitespace
        text = re.sub(r'\s+', ' ', text)
        # Strip punctuation except hyphens (keep word boundaries)
        text = re.sub(r'[^\w\s-]', '', text)
        return text.strip()
    
    @staticmethod
    def _tokenize(text: str) -> List[str]:
        """Tokenize normalized text into words."""
        # Split on whitespace and filter empty
        tokens = [t for t in text.split() if t]
        return tokens
    
    def find_candidates(self, sentence_norm: str, sentence_tokens: List[str]) -> List[MatchCandidate]:
        """
        Generate candidate matches for a normalized sentence.
        
        Returns candidates sorted by priority (exact > token > fuzzy).
        """
        candidates: List[MatchCandidate] = []
        sentence_norm_lower = sentence_norm.lower()
        
        # 1. Exact phrase matches (multi-word terms)
        for entry in self.multi_token_entries:
            if entry.normalized_term in sentence_norm_lower:
                candidates.append(MatchCandidate(
                    term=entry.original_term,
                    entity_type=entry.entity_type,
                    normalized_term=entry.normalized_term,
                    tokens=entry.tokens,
                    match_type="exact",
                ))
        
        # 2. Token-based matching
        # For single-token terms: require whole word match
        sentence_token_set = set(sentence_tokens)
        for entry in self.single_token_entries:
            if entry.tokens[0] in sentence_token_set:
                # Verify it's a whole word in the sentence
                pattern = r'\b' + re.escape(entry.tokens[0]) + r'\b'
                if re.search(pattern, sentence_norm_lower):
                    candidates.append(MatchCandidate(
                        term=entry.original_term,
                        entity_type=entry.entity_type,
                        normalized_term=entry.normalized_term,
                        tokens=entry.tokens,
                        match_type="token",
                    ))
        
        # For multi-token terms: require all tokens present, then confirm with substring
        for entry in self.multi_token_entries:
            if all(token in sentence_token_set for token in entry.tokens):
                # All tokens present, check if they form the phrase
                if entry.normalized_term in sentence_norm_lower:
                    # Avoid duplicates from exact match
                    if not any(c.normalized_term == entry.normalized_term and c.match_type == "exact" 
                              for c in candidates):
                        candidates.append(MatchCandidate(
                            term=entry.original_term,
                            entity_type=entry.entity_type,
                            normalized_term=entry.normalized_term,
                            tokens=entry.tokens,
                            match_type="token",
                        ))
        
        return candidates
    
    def find_fuzzy_candidates(self, sentence_norm: str, sentence_tokens: List[str], 
                             existing_candidates: List[MatchCandidate]) -> List[MatchCandidate]:
        """
        Generate fuzzy match candidates only if no exact/token matches found.
        
        This is a fallback that should be used sparingly.
        """
        if existing_candidates:
            return []  # Skip fuzzy if we have exact/token matches
        
        fuzzy_candidates: List[MatchCandidate] = []
        sentence_norm_lower = sentence_norm.lower()
        
        # Only check entries that have at least one token in common
        sentence_token_set = set(sentence_tokens)
        checked_entries = set()
        
        for token in sentence_tokens:
            if token in self.token_to_entries:
                for idx in self.token_to_entries[token]:
                    if idx in checked_entries:
                        continue
                    checked_entries.add(idx)
                    entry = self.entries[idx]
                    
                    # Quick substring check first
                    if entry.normalized_term in sentence_norm_lower:
                        continue  # Already matched exactly
                    
                    # For fuzzy, we'll let the caller use rapidfuzz
                    # Just mark it as a potential candidate
                    fuzzy_candidates.append(MatchCandidate(
                        term=entry.original_term,
                        entity_type=entry.entity_type,
                        normalized_term=entry.normalized_term,
                        tokens=entry.tokens,
                        match_type="fuzzy",
                    ))
        
        return fuzzy_candidates

