from __future__ import annotations
from dataclasses import dataclass
from typing import List, Tuple
import re
from rapidfuzz import fuzz

from src.lexicon import LEXICON
from src.search_index import LexiconIndex, MatchCandidate


@dataclass
class EntitySpan:
    span: str
    start: int
    end: int
    type: str
    score: float
    sentence_start: int
    sentence_end: int
    evidence: str


# Initialize index once at module load
_index = LexiconIndex(LEXICON)


def _normalize_for_match(s: str) -> str:
    """Normalize text for matching (same as LexiconIndex._normalize)."""
    from unidecode import unidecode
    text = unidecode(s.lower())
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'[^\w\s-]', '', text)
    return text.strip()


def _normalize_span(raw_text: str, start: int, end: int) -> tuple[int, int] | None:
    """
    Trim whitespace/punctuation and expand to full token boundaries.

    - Trims leading/trailing whitespace or punctuation.
    - Expands left/right while characters are alphanumeric (Unicode-aware).
    - Returns (start, end) or None if the span becomes invalid.
    """
    n = len(raw_text)
    # Clamp to valid range
    start = max(0, min(start, n))
    end = max(0, min(end, n))

    if start >= end:
        return None

    # Trim whitespace/punctuation at both ends
    while start < end and not raw_text[start].isalnum() and not raw_text[start].isspace() and not raw_text[start].isalpha():
        start += 1
    while end > start and not raw_text[end - 1].isalnum() and not raw_text[end - 1].isspace() and not raw_text[end - 1].isalpha():
        end -= 1

    # Also trim spaces
    while start < end and raw_text[start].isspace():
        start += 1
    while end > start and raw_text[end - 1].isspace():
        end -= 1

    if start >= end:
        return None

    # Expand to token boundaries (full words)
    while start > 0 and raw_text[start - 1].isalnum():
        start -= 1
    while end < n and raw_text[end].isalnum():
        end += 1

    if start >= end:
        return None

    return start, end

def _find_span_in_original(original_text: str, normalized_text: str, 
                          normalized_pattern: str, start_offset: int = 0) -> Tuple[int, int] | None:
    """
    Find the span of a normalized pattern in the original text.
    
    Returns (start, end) in original text coordinates, or None if not found.
    """
    # Find in normalized text first
    norm_idx = normalized_text.find(normalized_pattern)
    if norm_idx == -1:
        return None
    
    # Search in original text by normalizing windows
    # This handles accents and punctuation differences
    pattern_lower = normalized_pattern.lower()
    pattern_len = len(normalized_pattern)
    
    # Search around the expected position with a sliding window
    search_start = max(0, norm_idx - 10)
    search_end = min(len(original_text), norm_idx + pattern_len + 20)
    
    best_match = None
    best_score = 0
    
    for i in range(search_start, search_end):
        # Try windows of different sizes around this position
        for window_size in range(pattern_len - 2, pattern_len + 5):
            if i + window_size > len(original_text):
                continue
            window = original_text[i:i+window_size]
            window_norm = _normalize_for_match(window)
            
            # Check if normalized pattern matches
            if pattern_lower in window_norm or window_norm in pattern_lower:
                # Calculate a simple score (prefer exact length matches)
                score = 1.0 if len(window) == pattern_len else 0.8
                if score > best_score:
                    best_score = score
                    # Find the exact position within the window
                    window_idx = window_norm.find(pattern_lower)
                    if window_idx == -1:
                        # Try reverse
                        if pattern_lower.find(window_norm) != -1:
                            window_idx = 0
                    if window_idx != -1:
                        best_match = (start_offset + i + window_idx, 
                                     start_offset + i + window_idx + pattern_len)
    
    if best_match:
        return best_match
    
    # Fallback: approximate position
    return (start_offset + norm_idx, start_offset + norm_idx + pattern_len)


def _resolve_overlaps(spans: List[EntitySpan]) -> List[EntitySpan]:
    """
    Intelligently resolve overlapping spans.
    
    Rules:
    - Prefer longer spans over shorter when they overlap heavily
    - Keep higher score ties
    - Remove exact duplicates
    """
    if not spans:
        return []
    
    # Sort by start, then by length (desc), then by score (desc)
    sorted_spans = sorted(spans, key=lambda x: (x.start, -(x.end - x.start), -x.score))
    
    resolved = []
    for span in sorted_spans:
        # Check for overlaps with existing spans
        overlap_found = False
        for existing in resolved:
            # Check if they overlap significantly
            overlap_start = max(span.start, existing.start)
            overlap_end = min(span.end, existing.end)
            if overlap_start < overlap_end:
                # They overlap
                span_len = span.end - span.start
                existing_len = existing.end - existing.start
                overlap_len = overlap_end - overlap_start
                
                # If overlap is significant (>50% of shorter span), resolve
                min_len = min(span_len, existing_len)
                if overlap_len > 0.5 * min_len:
                    # Prefer longer span, or higher score if similar length
                    if span_len > existing_len * 1.2:
                        # Span is significantly longer, replace
                        resolved.remove(existing)
                        resolved.append(span)
                        overlap_found = True
                        break
                    elif span_len < existing_len * 0.8:
                        # Existing is longer, skip this span
                        overlap_found = True
                        break
                    elif span.score > existing.score:
                        # Similar length, prefer higher score
                        resolved.remove(existing)
                        resolved.append(span)
                        overlap_found = True
                        break
                    else:
                        # Existing is better, skip this span
                        overlap_found = True
                        break
        
        if not overlap_found:
            resolved.append(span)
    
    return sorted(resolved, key=lambda x: (x.start, -x.score))


def extract_entities_baseline(text: str, sentences: List[Tuple[str, int, int]], 
                              min_fuzzy: int = 90, enable_fuzzy: bool = True) -> List[EntitySpan]:
    """
    Extract entities using layered retrieval strategy.
    
    Args:
        text: Original text (preserves accents)
        sentences: List of (sent_text, sent_start, sent_end) tuples
        min_fuzzy: Minimum fuzzy match score (0-100)
        enable_fuzzy: Whether to enable fuzzy fallback
    
    Returns:
        List of EntitySpan objects with deduplicated overlaps
    """
    results: List[EntitySpan] = []
    
    # 1) Regex patterns (high precision)
    regex_patterns = [
        (re.compile(r"\bFAST\b", re.IGNORECASE), "PROCEDURE", 0.95),
    ]
    
    for sent_text, ss, se in sentences:
        for pat, etype, score in regex_patterns:
            for m in pat.finditer(sent_text):
                start = ss + m.start()
                end = ss + m.end()
                norm = _normalize_span(text, start, end)
                if not norm:
                    continue
                n_start, n_end = norm
                results.append(EntitySpan(
                    span=text[n_start:n_end],
                    start=n_start,
                    end=n_end,
                    type=etype,
                    score=score,
                    sentence_start=ss,
                    sentence_end=se,
                    evidence=sent_text.strip(),
                ))
    
    # 2) Lexicon-based matching using index
    for sent_text, ss, se in sentences:
        sent_norm = _normalize_for_match(sent_text)
        sent_tokens = sent_norm.split()
        
        # Get candidates from index
        candidates = _index.find_candidates(sent_norm, sent_tokens)
        
        # Process exact and token matches
        for cand in candidates:
            if cand.match_type in ("exact", "token"):
                # Find span in original text
                span_info = _find_span_in_original(sent_text, sent_norm, cand.normalized_term, ss)
                if span_info:
                    start, end = span_info
                    # Ensure we don't go beyond sentence bounds
                    start = max(ss, start)
                    end = min(se, end)

                    norm = _normalize_span(text, start, end)
                    if not norm:
                        continue
                    n_start, n_end = norm

                    if n_start < n_end:
                        score = 0.99 if cand.match_type == "exact" else 0.95
                        results.append(EntitySpan(
                            span=text[n_start:n_end],
                            start=n_start,
                            end=n_end,
                            type=cand.entity_type,
                            score=score,
                            sentence_start=ss,
                            sentence_end=se,
                            evidence=sent_text.strip(),
                        ))
        
        # 3) Fuzzy fallback (only if no exact/token matches and enabled)
        if enable_fuzzy and not any(c.match_type in ("exact", "token") for c in candidates):
            fuzzy_candidates = _index.find_fuzzy_candidates(sent_norm, sent_tokens, candidates)
            
            for cand in fuzzy_candidates:
                # Use rapidfuzz to find best match
                # Compare against sentence substrings
                best_score = 0
                best_start = None
                best_end = None
                
                # Try matching against sentence n-grams
                n = len(cand.tokens)
                if n > 0 and len(sent_tokens) >= n:
                    for i in range(len(sent_tokens) - n + 1):
                        window = " ".join(sent_tokens[i:i+n])
                        score = fuzz.partial_ratio(cand.normalized_term, window)
                        if score > best_score:
                            best_score = score
                            # Approximate position
                            window_text = " ".join(sent_tokens[i:i+n])
                            pos = sent_norm.find(window_text)
                            if pos != -1:
                                best_start = ss + pos
                                best_end = min(se, best_start + len(window_text))
                
                # Also try whole sentence match
                whole_score = fuzz.partial_ratio(cand.normalized_term, sent_norm)
                if whole_score > best_score:
                    best_score = whole_score
                    # Find approximate position
                    span_info = _find_span_in_original(sent_text, sent_norm, cand.normalized_term, ss)
                    if span_info:
                        best_start, best_end = span_info
                
                if best_score >= min_fuzzy and best_start is not None and best_end is not None:
                    norm = _normalize_span(text, best_start, best_end)
                    if not norm:
                        continue
                    n_start, n_end = norm
                    results.append(EntitySpan(
                        span=text[n_start:n_end],
                        start=n_start,
                        end=n_end,
                        type=cand.entity_type,
                        score=best_score / 100.0,
                        sentence_start=ss,
                        sentence_end=se,
                        evidence=sent_text.strip(),
                    ))
    
    # 4) Remove exact duplicates (same start/end/type)
    uniq = {}
    for e in results:
        key = (e.start, e.end, e.type)
        if key not in uniq or e.score > uniq[key].score:
            uniq[key] = e
    
    # 5) Resolve overlaps intelligently
    deduped = list(uniq.values())
    resolved = _resolve_overlaps(deduped)
    
    return sorted(resolved, key=lambda x: (x.start, -x.score))
