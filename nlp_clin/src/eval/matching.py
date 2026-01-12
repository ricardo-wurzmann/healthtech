"""
Entity matching functions for evaluation.

Supports strict and relaxed matching strategies.
"""
from __future__ import annotations
from typing import List, Tuple, Optional
from dataclasses import dataclass
from enum import Enum

# Import with fallback for both relative and absolute imports
try:
    from .schema import GoldEntity, PredEntity
except ImportError:
    from eval.schema import GoldEntity, PredEntity


class MatchMode(str, Enum):
    """Matching mode for relaxed evaluation."""
    IOU = "iou"  # IoU only (original behavior)
    IOU_OR_MIN_COV = "iou_or_min_cov"  # IoU or min coverage
    IOU_OR_CONTAINMENT = "iou_or_containment"  # IoU or containment
    IOU_OR_MIN_COV_OR_CONTAINMENT = "iou_or_min_cov_or_containment"  # All three


@dataclass
class Match:
    """Represents a matched pair of gold and predicted entities."""
    gold: GoldEntity
    pred: PredEntity
    match_type: str  # "strict" or "relaxed"
    match_reason: Optional[str] = None  # "iou", "min_cov", "containment", or None for strict


def compute_overlap(start1: int, end1: int, start2: int, end2: int) -> float:
    """
    Compute overlap ratio (IoU) between two spans.
    
    Args:
        start1, end1: First span
        start2, end2: Second span
    
    Returns:
        Overlap ratio (0.0 to 1.0)
    """
    overlap_start = max(start1, start2)
    overlap_end = min(end1, end2)
    
    if overlap_start >= overlap_end:
        return 0.0
    
    overlap_len = overlap_end - overlap_start
    span1_len = end1 - start1
    span2_len = end2 - start2
    union_len = span1_len + span2_len - overlap_len
    
    if union_len == 0:
        return 1.0
    
    return overlap_len / union_len


def compute_overlap_ratio(start1: int, end1: int, start2: int, end2: int) -> float:
    """
    Compute overlap as ratio of shorter span (alternative metric).
    
    Returns overlap length / min(span1_len, span2_len)
    """
    overlap_start = max(start1, start2)
    overlap_end = min(end1, end2)
    
    if overlap_start >= overlap_end:
        return 0.0
    
    overlap_len = overlap_end - overlap_start
    span1_len = end1 - start1
    span2_len = end2 - start2
    min_len = min(span1_len, span2_len)
    
    if min_len == 0:
        return 1.0 if overlap_len > 0 else 0.0
    
    return overlap_len / min_len


def compute_span_metrics(start1: int, end1: int, start2: int, end2: int) -> Tuple[float, float, int, bool]:
    """
    Compute comprehensive span matching metrics.
    
    Returns:
        Tuple of (iou, min_cov, intersection, is_containment)
    """
    intersection_start = max(start1, start2)
    intersection_end = min(end1, end2)
    intersection = max(0, intersection_end - intersection_start)
    
    len1 = end1 - start1
    len2 = end2 - start2
    
    # IoU
    union = len1 + len2 - intersection
    iou = intersection / union if union > 0 else 0.0
    
    # Min coverage (coverage of shorter span)
    min_len = min(len1, len2)
    min_cov = intersection / min_len if min_len > 0 else 0.0
    
    # Containment check
    is_containment = False
    if intersection > 0:
        # P contained in G: P.start >= G.start and P.end <= G.end
        # G contained in P: G.start >= P.start and G.end <= P.end
        if (start1 >= start2 and end1 <= end2) or (start2 >= start1 and end2 <= end1):
            is_containment = True
    
    return iou, min_cov, intersection, is_containment


def strict_match(gold: GoldEntity, pred: PredEntity) -> bool:
    """
    Check if gold and pred entities match strictly.
    
    Strict match requires:
    - Exact same start offset
    - Exact same end offset
    - Same entity type (after normalization)
    """
    return (
        gold.start == pred.start and
        gold.end == pred.end and
        gold.type == pred.type
    )


def relaxed_match(
    gold: GoldEntity, 
    pred: PredEntity, 
    overlap_threshold: float = 0.5,
    match_mode: MatchMode = MatchMode.IOU,
) -> Tuple[bool, Optional[str]]:
    """
    Check if gold and pred entities match with relaxed criteria.
    
    Relaxed match requires:
    - Same entity type (after normalization)
    - One of: IoU >= threshold, min_cov >= threshold, or containment
    
    Args:
        gold: Gold entity
        pred: Predicted entity
        overlap_threshold: Minimum overlap ratio (0.0 to 1.0)
        match_mode: Matching mode (IOU, IOU_OR_MIN_COV, IOU_OR_CONTAINMENT, IOU_OR_MIN_COV_OR_CONTAINMENT)
    
    Returns:
        Tuple of (is_match, match_reason) where reason is "iou", "min_cov", "containment", or None
    """
    if gold.type != pred.type:
        return False, None
    
    iou, min_cov, intersection, is_containment = compute_span_metrics(
        pred.start, pred.end, gold.start, gold.end
    )
    
    # Check matching conditions based on mode
    if match_mode == MatchMode.IOU:
        if iou >= overlap_threshold:
            return True, "iou"
        return False, None
    
    elif match_mode == MatchMode.IOU_OR_MIN_COV:
        if iou >= overlap_threshold:
            return True, "iou"
        if min_cov >= overlap_threshold:
            return True, "min_cov"
        return False, None
    
    elif match_mode == MatchMode.IOU_OR_CONTAINMENT:
        if iou >= overlap_threshold:
            return True, "iou"
        if is_containment and intersection > 0:
            return True, "containment"
        return False, None
    
    elif match_mode == MatchMode.IOU_OR_MIN_COV_OR_CONTAINMENT:
        if iou >= overlap_threshold:
            return True, "iou"
        if min_cov >= overlap_threshold:
            return True, "min_cov"
        if is_containment and intersection > 0:
            return True, "containment"
        return False, None
    
    else:
        # Fallback to IoU
        if iou >= overlap_threshold:
            return True, "iou"
        return False, None


def compute_match_score(
    gold: GoldEntity,
    pred: PredEntity,
) -> Tuple[float, int, int]:
    """
    Compute match score for tie-breaking.
    
    Returns:
        Tuple of (primary_score, intersection, start_distance)
        - primary_score: max(iou, min_cov)
        - intersection: overlap length
        - start_distance: abs(P.start - G.start)
    """
    iou, min_cov, intersection, _ = compute_span_metrics(
        pred.start, pred.end, gold.start, gold.end
    )
    primary_score = max(iou, min_cov)
    start_distance = abs(pred.start - gold.start)
    return primary_score, intersection, start_distance


def match_entities(
    gold_entities: List[GoldEntity],
    pred_entities: List[PredEntity],
    relaxed: bool = False,
    overlap_threshold: float = 0.5,
    use_iou: bool = True,
    match_mode: Optional[MatchMode] = None,
) -> Tuple[List[Match], List[GoldEntity], List[PredEntity]]:
    """
    Match gold and predicted entities.
    
    Args:
        gold_entities: List of gold entities
        pred_entities: List of predicted entities
        relaxed: If True, use relaxed matching; if False, use strict
        overlap_threshold: Threshold for relaxed matching (0.0 to 1.0)
        use_iou: If True, use IoU for relaxed (deprecated, use match_mode instead)
        match_mode: Matching mode for relaxed evaluation (defaults to IOU if not set)
    
    Returns:
        Tuple of (matched_pairs, unmatched_gold, unmatched_pred)
    """
    matched: List[Match] = []
    unmatched_gold = gold_entities.copy()
    unmatched_pred = pred_entities.copy()
    
    # Determine match mode
    if relaxed:
        if match_mode is None:
            # Default: use legacy behavior if use_iou is False, otherwise IOU
            match_mode = MatchMode.IOU if use_iou else MatchMode.IOU_OR_MIN_COV
    else:
        match_mode = None  # Not used for strict matching
    
    # Try to match each gold entity
    for gold in gold_entities[:]:  # Copy to iterate safely
        best_match = None
        best_pred_idx = None
        best_match_reason = None
        best_score = None
        
        for idx, pred in enumerate(pred_entities):
            if pred in unmatched_pred:
                if relaxed:
                    is_match, match_reason = relaxed_match(
                        gold, pred, overlap_threshold, match_mode
                    )
                    if is_match:
                        # Compute score for tie-breaking
                        primary_score, intersection, start_distance = compute_match_score(gold, pred)
                        score_tuple = (primary_score, intersection, -start_distance)  # Negative for smaller distance
                        
                        if best_match is None:
                            best_match = pred
                            best_pred_idx = idx
                            best_match_reason = match_reason
                            best_score = score_tuple
                        else:
                            # Compare scores: prefer higher primary_score, then larger intersection, then smaller distance
                            if score_tuple > best_score:
                                best_match = pred
                                best_pred_idx = idx
                                best_match_reason = match_reason
                                best_score = score_tuple
                else:
                    if strict_match(gold, pred):
                        best_match = pred
                        best_pred_idx = idx
                        best_match_reason = None
                        break  # Strict match is unique
        
        if best_match is not None:
            matched.append(Match(
                gold=gold, 
                pred=best_match, 
                match_type="relaxed" if relaxed else "strict",
                match_reason=best_match_reason
            ))
            unmatched_gold.remove(gold)
            unmatched_pred.remove(best_match)
    
    return matched, unmatched_gold, unmatched_pred

