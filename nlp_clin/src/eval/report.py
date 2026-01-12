"""
Print readable evaluation report from report.json.

Usage:
    # From nlp_clin/ directory:
    python report.py --report report.json
    
    # Or from src/ directory:
    python -m eval.report --report report.json
"""
from __future__ import annotations
import json
import argparse
from pathlib import Path
from typing import Dict, Any


def print_ner_summary(report: Dict[str, Any]):
    """Print NER metrics summary."""
    ner = report["ner"]
    overall = ner["overall"]
    
    print("\n" + "=" * 70)
    print("NER EVALUATION SUMMARY")
    print("=" * 70)
    print(f"\nOverall Metrics:")
    print(f"  Precision: {overall['precision']:.3f}")
    print(f"  Recall:    {overall['recall']:.3f}")
    print(f"  F1 Score:   {overall['f1']:.3f}")
    print(f"\nCounts:")
    print(f"  True Positives:  {overall['tp']}")
    print(f"  False Positives: {overall['fp']}")
    print(f"  False Negatives: {overall['fn']}")
    
    # Per-type metrics
    per_type = ner.get("per_type", {})
    if per_type:
        print(f"\nPer-Type Metrics:")
        print(f"  {'Type':<15} {'Precision':<12} {'Recall':<12} {'F1':<12} {'TP':<6} {'FP':<6} {'FN':<6}")
        print(f"  {'-' * 15} {'-' * 12} {'-' * 12} {'-' * 12} {'-' * 6} {'-' * 6} {'-' * 6}")
        
        # Sort by F1 descending
        sorted_types = sorted(
            per_type.items(),
            key=lambda x: x[1]["f1"],
            reverse=True
        )
        
        for entity_type, metrics in sorted_types:
            print(f"  {entity_type:<15} {metrics['precision']:>11.3f} {metrics['recall']:>11.3f} "
                  f"{metrics['f1']:>11.3f} {metrics['tp']:>5} {metrics['fp']:>5} {metrics['fn']:>5}")


def print_assertion_summary(report: Dict[str, Any]):
    """Print assertion metrics summary."""
    assertion = report["assertion"]
    
    print("\n" + "=" * 70)
    print("ASSERTION CLASSIFICATION SUMMARY")
    print("=" * 70)
    print(f"\nAccuracy: {assertion['accuracy']:.3f}")
    print(f"Total Matched Entities: {assertion['total_matched']}")
    
    # Confusion matrix
    cm = assertion["confusion_matrix"]
    if cm:
        print(f"\nConfusion Matrix:")
        labels = sorted(set(cm.keys()) | set(l for row in cm.values() for l in row.keys()))
        
        # Header
        header = "Gold\\Pred"
        print(f"  {header:<15}", end="")
        for label in labels:
            print(f" {label:<12}", end="")
        print()
        print(f"  {'-' * 15}", end="")
        for _ in labels:
            print(f" {'-' * 12}", end="")
        print()
        
        # Rows
        for gold_label in labels:
            if gold_label in cm:
                print(f"  {gold_label:<15}", end="")
                for pred_label in labels:
                    count = cm[gold_label].get(pred_label, 0)
                    print(f" {count:>11} ", end="")
                print()


def print_coverage_summary(report: Dict[str, Any]):
    """Print coverage metrics summary."""
    coverage = report["coverage"]
    
    print("\n" + "=" * 70)
    print("COVERAGE SUMMARY")
    print("=" * 70)
    print(f"\nCases:")
    print(f"  Total: {coverage['total_cases']}")
    print(f"  With entities: {coverage['cases_with_entities']} "
          f"({coverage['pct_cases_with_entities']:.1f}%)")
    print(f"  Without entities: {coverage['cases_without_entities']}")
    print(f"\nAverage entities per case: {coverage['avg_entities_per_case']:.2f}")
    
    # Entity type distribution
    type_dist = coverage.get("entity_type_distribution", {})
    if type_dist:
        print(f"\nEntity Type Distribution:")
        sorted_types = sorted(type_dist.items(), key=lambda x: x[1], reverse=True)
        for entity_type, count in sorted_types:
            print(f"  {entity_type:<15} {count:>5}")
    
    # Top entity texts
    top_texts = coverage.get("top_entity_texts", [])
    if top_texts:
        print(f"\nTop Entity Texts (top 10):")
        for item in top_texts[:10]:
            text = item.get("text", "") if isinstance(item, dict) else item[0]
            count = item.get("count", 0) if isinstance(item, dict) else item[1]
            # Truncate long texts
            text_display = text[:40] + "..." if len(text) > 40 else text
            print(f"  {text_display:<43} {count:>5}")


def print_error_examples(report: Dict[str, Any]):
    """Print error examples."""
    errors = report.get("errors", {})
    
    # False positives
    fps = errors.get("false_positives", [])
    if fps:
        print("\n" + "=" * 70)
        print("FALSE POSITIVES (Top Examples)")
        print("=" * 70)
        for i, fp in enumerate(fps[:5], 1):
            print(f"\n{i}. Case: {fp['case_id']}")
            print(f"   Text: '{fp['text']}'")
            print(f"   Type: {fp['type']}")
            print(f"   Score: {fp.get('score', 0):.3f}")
            if fp.get('evidence'):
                evidence = fp['evidence'][:100] + "..." if len(fp['evidence']) > 100 else fp['evidence']
                print(f"   Evidence: {evidence}")
    
    # False negatives
    fns = errors.get("false_negatives", [])
    if fns:
        print("\n" + "=" * 70)
        print("FALSE NEGATIVES (Top Examples)")
        print("=" * 70)
        for i, fn in enumerate(fns[:5], 1):
            print(f"\n{i}. Case: {fn['case_id']}")
            print(f"   Text: '{fn['text']}'")
            print(f"   Type: {fn['type']}")
            if fn.get('context'):
                context = fn['context'][:100] + "..." if len(fn['context']) > 100 else fn['context']
                print(f"   Context: {context}")
    
    # Assertion mismatches
    assertion_errors = errors.get("assertion_mismatches", [])
    if assertion_errors:
        print("\n" + "=" * 70)
        print("ASSERTION MISMATCHES (Top Examples)")
        print("=" * 70)
        for i, err in enumerate(assertion_errors[:5], 1):
            print(f"\n{i}. Case: {err['case_id']}")
            print(f"   Entity: '{err['text']}' ({err['type']})")
            print(f"   Gold: {err['gold_assertion']} | Predicted: {err['pred_assertion']}")
            if err.get('evidence'):
                evidence = err['evidence'][:100] + "..." if len(err['evidence']) > 100 else err['evidence']
                print(f"   Evidence: {evidence}")


def main():
    parser = argparse.ArgumentParser(description="Print readable evaluation report")
    parser.add_argument(
        "--report",
        type=str,
        required=True,
        help="Path to report JSON file"
    )
    parser.add_argument(
        "--no-errors",
        action="store_true",
        help="Skip printing error examples"
    )
    
    args = parser.parse_args()
    
    # Load report
    with open(args.report, 'r', encoding='utf-8') as f:
        report = json.load(f)
    
    # Print config
    config = report.get("config", {})
    print("=" * 70)
    print("EVALUATION REPORT")
    print("=" * 70)
    print(f"\nConfiguration:")
    print(f"  Matching: {'Relaxed' if config.get('relaxed_matching') else 'Strict'}")
    if config.get('relaxed_matching'):
        print(f"  Overlap threshold: {config.get('overlap_threshold', 0.5)}")
        print(f"  Metric: {'IoU' if config.get('use_iou') else 'Overlap/MinLength'}")
    print(f"  Total cases evaluated: {config.get('total_cases', 0)}")
    
    # Print summaries
    print_ner_summary(report)
    print_assertion_summary(report)
    print_coverage_summary(report)
    
    if not args.no_errors:
        print_error_examples(report)
    
    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()

