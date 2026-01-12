"""
Main evaluation script.

Usage:
    # From nlp_clin/ directory:
    python evaluate.py --pred predictions.json --gold gold.jsonl --out report.json
    python evaluate.py --pred predictions.json --gold gold.jsonl --out report.json --relaxed --overlap 0.5
    
    # Or from src/ directory:
    python -m eval.evaluate --pred predictions.json --gold gold.jsonl --out report.json
"""
from __future__ import annotations
import json
import argparse
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

# Import with fallback for both relative and absolute imports
try:
    from .schema import GoldCase, PredCase, GoldEntity, PredEntity
    from .matching import match_entities, MatchMode
    from .metrics import (
        compute_ner_metrics,
        compute_per_type_metrics,
        compute_assertion_metrics,
        compute_coverage_metrics,
        collect_error_examples,
    )
except ImportError:
    from eval.schema import GoldCase, PredCase, GoldEntity, PredEntity
    from eval.matching import match_entities, MatchMode
    from eval.metrics import (
        compute_ner_metrics,
        compute_per_type_metrics,
        compute_assertion_metrics,
        compute_coverage_metrics,
        collect_error_examples,
    )


def load_gold_cases(gold_path: Path) -> List[GoldCase]:
    """Load gold cases from JSONL file."""
    cases = []
    with open(gold_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            case_dict = json.loads(line)
            cases.append(GoldCase.from_dict(case_dict))
    return cases


def load_pred_cases(pred_path: Path) -> List[PredCase]:
    """Load predicted cases from JSON file."""
    with open(pred_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Handle different formats
    if isinstance(data, list):
        return [PredCase.from_dict(case) for case in data]
    elif isinstance(data, dict):
        # Could be single case or dict of cases
        if "case_id" in data or "doc_id" in data:
            return [PredCase.from_dict(data)]
        else:
            # Assume dict of cases: {case_id: case_data}
            return [PredCase.from_dict(case) for case in data.values()]
    else:
        raise ValueError(f"Unexpected predictions format: {type(data)}")


def align_cases(gold_cases: List[GoldCase], pred_cases: List[PredCase]) -> List[Tuple[GoldCase, PredCase]]:
    """
    Align gold and predicted cases by case_id.
    
    Returns:
        List of (gold_case, pred_case) tuples
    """
    # Build lookup dictionaries
    gold_dict = {str(case.case_id): case for case in gold_cases}
    pred_dict = {str(case.case_id): case for case in pred_cases}
    
    # Find matches
    aligned = []
    missing_gold = []
    missing_pred = []
    
    for case_id, gold_case in gold_dict.items():
        if case_id in pred_dict:
            aligned.append((gold_case, pred_dict[case_id]))
        else:
            missing_pred.append(case_id)
    
    for case_id, pred_case in pred_dict.items():
        if case_id not in gold_dict:
            missing_gold.append(case_id)
    
    # Warn about mismatches
    if missing_gold:
        print(f"Warning: {len(missing_gold)} predicted cases have no gold annotation: {missing_gold[:5]}...")
    if missing_pred:
        print(f"Warning: {len(missing_pred)} gold cases have no predictions: {missing_pred[:5]}...")
    
    return aligned


def evaluate(
    gold_cases: List[GoldCase],
    pred_cases: List[PredCase],
    relaxed: bool = False,
    overlap_threshold: float = 0.5,
    use_iou: bool = True,
    match_mode: Optional[MatchMode] = None,
) -> Dict[str, Any]:
    """
    Run full evaluation.
    
    Returns:
        Dictionary with all metrics and error examples
    """
    # Align cases
    aligned = align_cases(gold_cases, pred_cases)
    
    if not aligned:
        raise ValueError("No cases could be aligned between gold and predictions")
    
    # Collect all entities and debug counters
    all_matched: List = []
    all_unmatched_gold: List[GoldEntity] = []
    all_unmatched_pred: List[PredEntity] = []

    total_gold_entities_loaded = 0
    total_pred_entities_loaded = 0
    total_gold_entities_with_missing_offsets = 0
    total_matches_found = 0
    
    for gold_case, pred_case in aligned:
        # Get text for evaluation (should be consistent)
        gold_text = gold_case.raw_text
        pred_text = pred_case.get_text_for_evaluation()
        
        # Warn if texts differ significantly
        if abs(len(gold_text) - len(pred_text)) > 10:
            print(f"Warning: Text length mismatch for case {gold_case.case_id}: "
                  f"gold={len(gold_text)}, pred={len(pred_text)}")

        # Count loaded entities
        total_gold_entities_loaded += len(gold_case.gold_entities)
        total_pred_entities_loaded += len(pred_case.entities)

        # Filter entities with valid offsets (skip None offsets)
        valid_gold_entities: List[GoldEntity] = []
        for e in gold_case.gold_entities:
            if isinstance(e.start, int) and isinstance(e.end, int):
                valid_gold_entities.append(e)
            else:
                total_gold_entities_with_missing_offsets += 1

        valid_pred_entities: List[PredEntity] = []
        for e in pred_case.entities:
            if isinstance(e.start, int) and isinstance(e.end, int):
                valid_pred_entities.append(e)
            else:
                # Predictions without offsets are ignored
                continue

        # Match entities (only those with valid offsets)
        matched, unmatched_gold, unmatched_pred = match_entities(
            valid_gold_entities,
            valid_pred_entities,
            relaxed=relaxed,
            overlap_threshold=overlap_threshold,
            use_iou=use_iou,
            match_mode=match_mode,
        )

        total_matches_found += len(matched)

        all_matched.extend(matched)
        all_unmatched_gold.extend(unmatched_gold)
        all_unmatched_pred.extend(unmatched_pred)
    
    # Compute metrics
    ner_metrics = compute_ner_metrics(all_matched, all_unmatched_gold, all_unmatched_pred)
    type_metrics = compute_per_type_metrics(all_matched, all_unmatched_gold, all_unmatched_pred)
    assertion_metrics = compute_assertion_metrics(all_matched)
    coverage_metrics = compute_coverage_metrics(pred_cases)
    
    # Collect error examples
    error_examples = collect_error_examples(
        all_matched,
        all_unmatched_gold,
        all_unmatched_pred,
        gold_cases,
        pred_cases,
        max_examples=10,
    )
    
    # Count matches by reason
    matched_by_iou = sum(1 for m in all_matched if m.match_reason == "iou")
    matched_by_min_cov = sum(1 for m in all_matched if m.match_reason == "min_cov")
    matched_by_containment = sum(1 for m in all_matched if m.match_reason == "containment")
    
    # Build report
    report = {
        "config": {
            "relaxed_matching": relaxed,
            "overlap_threshold": overlap_threshold,
            "use_iou": use_iou,
            "match_mode": match_mode.value if match_mode else None,
            "total_cases": len(aligned),
            "total_gold_entities_loaded": total_gold_entities_loaded,
            "total_pred_entities_loaded": total_pred_entities_loaded,
            "total_gold_entities_with_missing_offsets": total_gold_entities_with_missing_offsets,
            "total_matches_found": total_matches_found,
            "matched_by_iou": matched_by_iou,
            "matched_by_min_cov": matched_by_min_cov,
            "matched_by_containment": matched_by_containment,
        },
        "ner": {
            "overall": {
                "precision": ner_metrics.precision,
                "recall": ner_metrics.recall,
                "f1": ner_metrics.f1,
                "tp": ner_metrics.tp,
                "fp": ner_metrics.fp,
                "fn": ner_metrics.fn,
            },
            "per_type": {
                entity_type: {
                    "precision": metrics.precision,
                    "recall": metrics.recall,
                    "f1": metrics.f1,
                    "tp": metrics.tp,
                    "fp": metrics.fp,
                    "fn": metrics.fn,
                }
                for entity_type, metrics in type_metrics.items()
            },
        },
        "assertion": {
            "accuracy": assertion_metrics.accuracy,
            "confusion_matrix": assertion_metrics.confusion_matrix,
            "total_matched": assertion_metrics.total_matched,
        },
        "coverage": {
            "total_cases": coverage_metrics.total_cases,
            "cases_with_entities": coverage_metrics.cases_with_entities,
            "cases_without_entities": coverage_metrics.cases_without_entities,
            "pct_cases_with_entities": (
                coverage_metrics.cases_with_entities / coverage_metrics.total_cases * 100
                if coverage_metrics.total_cases > 0 else 0.0
            ),
            "avg_entities_per_case": coverage_metrics.avg_entities_per_case,
            "entity_type_distribution": coverage_metrics.entity_type_distribution,
            "top_entity_texts": [
                {"text": text, "count": count}
                for text, count in coverage_metrics.top_entity_texts
            ],
        },
        "errors": error_examples,
    }
    
    return report


def main():
    parser = argparse.ArgumentParser(description="Evaluate predictions against gold standard")
    parser.add_argument(
        "--pred",
        type=str,
        required=True,
        help="Path to predictions JSON file"
    )
    parser.add_argument(
        "--gold",
        type=str,
        required=True,
        help="Path to gold annotations JSONL file"
    )
    parser.add_argument(
        "--out",
        type=str,
        required=True,
        help="Path to output report JSON file"
    )
    parser.add_argument(
        "--relaxed",
        action="store_true",
        help="Use relaxed matching (overlap-based) instead of strict"
    )
    parser.add_argument(
        "--overlap",
        type=float,
        default=0.5,
        help="Overlap threshold for relaxed matching (default: 0.5)"
    )
    parser.add_argument(
        "--no-iou",
        action="store_true",
        help="Use overlap/min_length ratio instead of IoU for relaxed matching (deprecated, use --match-mode)"
    )
    parser.add_argument(
        "--match-mode",
        type=str,
        choices=["iou", "iou_or_min_cov", "iou_or_containment", "iou_or_min_cov_or_containment"],
        default=None,
        help="Matching mode for relaxed evaluation. Default: 'iou' if --relaxed, or 'iou_or_min_cov_or_containment' if --relaxed and not --no-iou"
    )
    
    args = parser.parse_args()
    
    # Load data
    print(f"Loading gold annotations from {args.gold}...")
    gold_cases = load_gold_cases(Path(args.gold))
    print(f"  Loaded {len(gold_cases)} gold cases")
    
    print(f"Loading predictions from {args.pred}...")
    pred_cases = load_pred_cases(Path(args.pred))
    print(f"  Loaded {len(pred_cases)} predicted cases")
    
    # Determine match mode
    match_mode = None
    if args.match_mode:
        match_mode = MatchMode(args.match_mode)
    elif args.relaxed:
        # Default for relaxed: use iou_or_min_cov_or_containment unless --no-iou is set
        if args.no_iou:
            match_mode = MatchMode.IOU_OR_MIN_COV
        else:
            match_mode = MatchMode.IOU_OR_MIN_COV_OR_CONTAINMENT
    
    # Run evaluation
    print(f"\nRunning evaluation (relaxed={args.relaxed}, overlap={args.overlap}, match_mode={match_mode.value if match_mode else None})...")
    report = evaluate(
        gold_cases,
        pred_cases,
        relaxed=args.relaxed,
        overlap_threshold=args.overlap,
        use_iou=not args.no_iou,
        match_mode=match_mode,
    )
    
    # Save report
    output_path = Path(args.out)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    print(f"\nEvaluation complete!")
    print(f"  Overall F1: {report['ner']['overall']['f1']:.3f}")
    print(f"  Precision: {report['ner']['overall']['precision']:.3f}")
    print(f"  Recall: {report['ner']['overall']['recall']:.3f}")
    print(f"  Assertion Accuracy: {report['assertion']['accuracy']:.3f}")
    print(f"\nReport saved to {output_path}")


if __name__ == "__main__":
    main()

