"""
Metrics computation for NER, assertion, and coverage evaluation.
"""
from __future__ import annotations
from typing import List, Dict, Any, Tuple, Counter
from collections import defaultdict, Counter
from dataclasses import dataclass

# Import with fallback for both relative and absolute imports
try:
    from .schema import GoldCase, PredCase, GoldEntity, PredEntity
    from .matching import Match, match_entities
except ImportError:
    from eval.schema import GoldCase, PredCase, GoldEntity, PredEntity
    from eval.matching import Match, match_entities


@dataclass
class NERMetrics:
    """NER precision/recall/F1 metrics."""
    precision: float
    recall: float
    f1: float
    tp: int
    fp: int
    fn: int


@dataclass
class TypeMetrics:
    """Per-type NER metrics."""
    type: str
    precision: float
    recall: float
    f1: float
    tp: int
    fp: int
    fn: int


@dataclass
class AssertionMetrics:
    """Assertion classification metrics."""
    accuracy: float
    confusion_matrix: Dict[str, Dict[str, int]]
    total_matched: int


@dataclass
class CoverageMetrics:
    """Coverage and distribution metrics."""
    total_cases: int
    cases_with_entities: int
    cases_without_entities: int
    avg_entities_per_case: float
    entity_type_distribution: Dict[str, int]
    top_entity_texts: List[Tuple[str, int]]  # (text, count)


def compute_ner_metrics(
    matched: List[Match],
    unmatched_gold: List[GoldEntity],
    unmatched_pred: List[PredEntity],
) -> NERMetrics:
    """
    Compute overall NER metrics.
    
    Args:
        matched: List of matched entity pairs
        unmatched_gold: False negatives
        unmatched_pred: False positives
    
    Returns:
        NERMetrics object
    """
    tp = len(matched)
    fp = len(unmatched_pred)
    fn = len(unmatched_gold)
    
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    
    return NERMetrics(
        precision=precision,
        recall=recall,
        f1=f1,
        tp=tp,
        fp=fp,
        fn=fn,
    )


def compute_per_type_metrics(
    matched: List[Match],
    unmatched_gold: List[GoldEntity],
    unmatched_pred: List[PredEntity],
) -> Dict[str, TypeMetrics]:
    """
    Compute NER metrics per entity type.
    
    Returns:
        Dictionary mapping entity type to TypeMetrics
    """
    # Count by type
    tp_by_type: Dict[str, int] = defaultdict(int)
    fp_by_type: Dict[str, int] = defaultdict(int)
    fn_by_type: Dict[str, int] = defaultdict(int)
    
    # True positives (matched)
    for match in matched:
        tp_by_type[match.gold.type] += 1
    
    # False positives (unmatched predictions)
    for pred in unmatched_pred:
        fp_by_type[pred.type] += 1
    
    # False negatives (unmatched gold)
    for gold in unmatched_gold:
        fn_by_type[gold.type] += 1
    
    # Compute metrics per type
    type_metrics = {}
    all_types = set(tp_by_type.keys()) | set(fp_by_type.keys()) | set(fn_by_type.keys())
    
    for entity_type in all_types:
        tp = tp_by_type[entity_type]
        fp = fp_by_type[entity_type]
        fn = fn_by_type[entity_type]
        
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
        
        type_metrics[entity_type] = TypeMetrics(
            type=entity_type,
            precision=precision,
            recall=recall,
            f1=f1,
            tp=tp,
            fp=fp,
            fn=fn,
        )
    
    return type_metrics


def compute_assertion_metrics(
    matched: List[Match],
    assertion_labels: List[str] | None = None,
) -> AssertionMetrics:
    """
    Compute assertion classification metrics on matched entities.
    
    Args:
        matched: List of matched entity pairs
        assertion_labels: List of valid assertion labels (default: PRESENT, NEGATED, POSSIBLE, HISTORICAL)
    
    Returns:
        AssertionMetrics object
    """
    if assertion_labels is None:
        assertion_labels = ["PRESENT", "NEGATED", "POSSIBLE", "HISTORICAL"]
    
    # Build confusion matrix
    confusion_matrix: Dict[str, Dict[str, int]] = {
        label: {other: 0 for other in assertion_labels} for label in assertion_labels
    }
    
    correct = 0
    total = 0
    
    for match in matched:
        gold_assertion = match.gold.assertion or "PRESENT"  # Default if missing
        pred_assertion = match.pred.assertion or "PRESENT"
        
        # Normalize
        gold_assertion = gold_assertion.upper().strip()
        pred_assertion = pred_assertion.upper().strip()
        
        # Use PRESENT as default if not in valid labels
        if gold_assertion not in assertion_labels:
            gold_assertion = "PRESENT"
        if pred_assertion not in assertion_labels:
            pred_assertion = "PRESENT"
        
        confusion_matrix[gold_assertion][pred_assertion] += 1
        
        if gold_assertion == pred_assertion:
            correct += 1
        total += 1
    
    accuracy = correct / total if total > 0 else 0.0
    
    return AssertionMetrics(
        accuracy=accuracy,
        confusion_matrix=confusion_matrix,
        total_matched=total,
    )


def compute_coverage_metrics(
    pred_cases: List[PredCase],
) -> CoverageMetrics:
    """
    Compute coverage and distribution metrics.
    
    Args:
        pred_cases: List of predicted cases
    
    Returns:
        CoverageMetrics object
    """
    total_cases = len(pred_cases)
    cases_with_entities = sum(1 for case in pred_cases if case.entities)
    cases_without_entities = total_cases - cases_with_entities
    
    # Count total entities
    total_entities = sum(len(case.entities) for case in pred_cases)
    avg_entities_per_case = total_entities / total_cases if total_cases > 0 else 0.0
    
    # Entity type distribution
    type_counter: Counter[str] = Counter()
    text_counter: Counter[str] = Counter()
    
    for case in pred_cases:
        for ent in case.entities:
            type_counter[ent.type] += 1
            text_counter[ent.span.strip()] += 1
    
    # Top entity texts (limit to top 20)
    top_texts = text_counter.most_common(20)
    
    return CoverageMetrics(
        total_cases=total_cases,
        cases_with_entities=cases_with_entities,
        cases_without_entities=cases_without_entities,
        avg_entities_per_case=avg_entities_per_case,
        entity_type_distribution=dict(type_counter),
        top_entity_texts=top_texts,
    )


def collect_error_examples(
    matched: List[Match],
    unmatched_gold: List[GoldEntity],
    unmatched_pred: List[PredEntity],
    gold_cases: List[GoldCase],
    pred_cases: List[PredCase],
    max_examples: int = 10,
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Collect error examples for analysis.
    
    Returns:
        Dictionary with:
        - false_positives: List of FP examples
        - false_negatives: List of FN examples
        - assertion_mismatches: List of assertion errors
    """
    # Build case lookup and entity-to-case mapping
    gold_case_dict = {str(case.case_id): case for case in gold_cases}
    pred_case_dict = {str(case.case_id): case for case in pred_cases}
    
    # Build entity to case_id mapping for predictions (use tuple as key since entities aren't hashable)
    pred_entity_to_case: Dict[Tuple[int, int, str], str] = {}
    for case in pred_cases:
        case_id = str(case.case_id)
        for ent in case.entities:
            key = (ent.start, ent.end, ent.type)
            pred_entity_to_case[key] = case_id
    
    # Build entity to case_id mapping for gold
    gold_entity_to_case: Dict[Tuple[int, int, str], str] = {}
    for case in gold_cases:
        case_id = str(case.case_id)
        for ent in case.gold_entities:
            key = (ent.start, ent.end, ent.type)
            gold_entity_to_case[key] = case_id
    
    # False positives
    false_positives = []
    for pred in unmatched_pred[:max_examples]:
        key = (pred.start, pred.end, pred.type)
        case_id = pred_entity_to_case.get(key)
        if case_id:
            case = pred_case_dict.get(case_id)
            text = case.get_text_for_evaluation() if case else ""
            context = _get_context(text, pred.start, pred.end, window=50)
            
            false_positives.append({
                "case_id": case_id,
                "text": pred.span,
                "type": pred.type,
                "start": pred.start,
                "end": pred.end,
                "score": pred.score,
                "evidence": pred.evidence or context,
            })
    
    # False negatives
    false_negatives = []
    for gold in unmatched_gold[:max_examples]:
        key = (gold.start, gold.end, gold.type)
        case_id = gold_entity_to_case.get(key)
        if case_id:
            case = gold_case_dict.get(case_id)
            text = case.raw_text if case else ""
            context = _get_context(text, gold.start, gold.end, window=50)
            
            false_negatives.append({
                "case_id": case_id,
                "text": gold.text,
                "type": gold.type,
                "start": gold.start,
                "end": gold.end,
                "context": context,
            })
    
    # Assertion mismatches
    assertion_mismatches = []
    for match in matched:
        gold_assertion = match.gold.assertion or "PRESENT"
        pred_assertion = match.pred.assertion or "PRESENT"
        
        if gold_assertion.upper() != pred_assertion.upper():
            pred_key = (match.pred.start, match.pred.end, match.pred.type)
            gold_key = (match.gold.start, match.gold.end, match.gold.type)
            case_id = pred_entity_to_case.get(pred_key) or gold_entity_to_case.get(gold_key, "unknown")
            
            assertion_mismatches.append({
                "case_id": case_id,
                "text": match.gold.text,
                "type": match.gold.type,
                "gold_assertion": gold_assertion,
                "pred_assertion": pred_assertion,
                "evidence": match.pred.evidence or "",
            })
    
    return {
        "false_positives": false_positives[:max_examples],
        "false_negatives": false_negatives[:max_examples],
        "assertion_mismatches": assertion_mismatches[:max_examples],
    }


def _get_context(text: str, start: int | None, end: int | None, window: int = 50) -> str:
    """
    Extract context around a span.

    If start/end are missing or not integers, return a safe fallback
    (e.g., the first 120 characters) instead of raising.
    """
    if not text:
        return ""

    if not isinstance(start, int) or not isinstance(end, int):
        # Fallback: beginning of the text
        return text[: min(len(text), 120)]

    context_start = max(0, start - window)
    context_end = min(len(text), end + window)
    if context_start >= context_end:
        return text[: min(len(text), 120)]
    return text[context_start:context_end]

