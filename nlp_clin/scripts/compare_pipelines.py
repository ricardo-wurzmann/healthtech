"""
Compare baseline pipeline (run_pipeline.py) vs canonical pipeline (main_canonical.py)
"""
import argparse
import json
from pathlib import Path
from collections import Counter, defaultdict


def load_results(directory: Path):
    """Load all JSON results from directory."""
    results = {}
    for json_file in sorted(directory.glob("*.json")):
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            results[json_file.stem] = data
    return results


def compare_entities(baseline_ent, canonical_ent):
    """
    Compare two entity lists.
    
    Returns dict with:
    - only_baseline: entities only in baseline
    - only_canonical: entities only in canonical
    - in_both: entities in both systems
    """
    baseline_set = {(e['span'], e['type'], e['start']) for e in baseline_ent}
    canonical_set = {(e['span'], e['type'], e['start']) for e in canonical_ent}
    
    only_baseline = baseline_set - canonical_set
    only_canonical = canonical_set - baseline_set
    in_both = baseline_set & canonical_set
    
    return {
        'only_baseline': only_baseline,
        'only_canonical': only_canonical,
        'in_both': in_both
    }


def analyze_entity_types(baseline_results, canonical_results):
    """Analyze entity type distribution in both systems."""
    baseline_types = Counter()
    canonical_types = Counter()
    
    for doc_id in baseline_results:
        for ent in baseline_results[doc_id]['entities']:
            baseline_types[ent['type']] += 1
    
    for doc_id in canonical_results:
        if doc_id in baseline_results:
            for ent in canonical_results[doc_id]['entities']:
                canonical_types[ent['type']] += 1
    
    return baseline_types, canonical_types


def main():
    parser = argparse.ArgumentParser(
        description="Compare baseline pipeline vs canonical pipeline results."
    )
    parser.add_argument(
        "--baseline-dir",
        type=Path,
        default=None,
        help="Directory with baseline results (default: nlp_clin/data/processed/cases).",
    )
    parser.add_argument(
        "--canonical-dir",
        type=Path,
        default=None,
        help="Directory with canonical results (default: nlp_clin/data/processed/cases_canonical).",
    )
    args = parser.parse_args()

    nlp_clin_root = Path(__file__).parent.parent
    repo_root = nlp_clin_root.parent

    baseline_dir = args.baseline_dir or (nlp_clin_root / "data" / "processed" / "cases")
    canonical_dir = args.canonical_dir or (
        nlp_clin_root / "data" / "processed" / "cases_canonical"
    )

    # Fallback to repo-root data folder if defaults are missing
    if not baseline_dir.exists():
        repo_baseline = repo_root / "data" / "processed" / "cases"
        if repo_baseline.exists():
            baseline_dir = repo_baseline
            print(f"[INFO] Using baseline dir from repo root: {baseline_dir}")

    if not canonical_dir.exists():
        repo_canonical = repo_root / "data" / "processed" / "cases_canonical"
        if repo_canonical.exists():
            canonical_dir = repo_canonical
            print(f"[INFO] Using canonical dir from repo root: {canonical_dir}")
    
    print("="*60)
    print("COMPARING BASELINE vs CANONICAL NER")
    print("="*60)
    
    # Check directories exist
    if not baseline_dir.exists():
        print(f"[ERROR] Baseline directory not found: {baseline_dir}")
        print("Run baseline first: python src/run_pipeline.py")
        return
    
    if not canonical_dir.exists():
        print(f"[ERROR] Canonical directory not found: {canonical_dir}")
        print("Run canonical first: python main_canonical.py")
        return
    
    # Load results
    print(f"\nLoading results...")
    baseline_results = load_results(baseline_dir)
    canonical_results = load_results(canonical_dir)
    
    print(f"  Baseline cases: {len(baseline_results)}")
    print(f"  Canonical cases: {len(canonical_results)}")
    
    if not baseline_results or not canonical_results:
        print("[ERROR] No results found in one or both directories")
        return
    
    # Compare entity types
    print("\n" + "="*60)
    print("ENTITY TYPE DISTRIBUTION")
    print("="*60)
    
    baseline_types, canonical_types = analyze_entity_types(baseline_results, canonical_results)
    
    all_types = sorted(set(baseline_types.keys()) | set(canonical_types.keys()))
    
    print(f"\n{'Type':<15} {'Baseline':>10} {'Canonical':>10} {'Diff':>10}")
    print("-" * 50)
    for etype in all_types:
        b_count = baseline_types.get(etype, 0)
        c_count = canonical_types.get(etype, 0)
        diff = c_count - b_count
        diff_str = f"+{diff}" if diff > 0 else str(diff)
        print(f"{etype:<15} {b_count:>10} {c_count:>10} {diff_str:>10}")
    
    print("-" * 50)
    print(f"{'TOTAL':<15} {sum(baseline_types.values()):>10} {sum(canonical_types.values()):>10}")
    
    # Per-document comparison
    print("\n" + "="*60)
    print("PER-DOCUMENT COMPARISON")
    print("="*60)
    
    total_only_baseline = 0
    total_only_canonical = 0
    total_both = 0
    
    doc_comparisons = []
    
    for doc_id in sorted(baseline_results.keys()):
        if doc_id not in canonical_results:
            print(f"[WARNING] Missing in canonical: {doc_id}")
            continue
        
        baseline_doc = baseline_results[doc_id]
        canonical_doc = canonical_results[doc_id]
        
        comparison = compare_entities(
            baseline_doc['entities'],
            canonical_doc['entities']
        )
        
        total_only_baseline += len(comparison['only_baseline'])
        total_only_canonical += len(comparison['only_canonical'])
        total_both += len(comparison['in_both'])
        
        doc_comparisons.append({
            'doc_id': doc_id,
            'comparison': comparison,
            'baseline_count': len(baseline_doc['entities']),
            'canonical_count': len(canonical_doc['entities'])
        })
    
    # Show summary for first 5 documents
    print(f"\nShowing first 5 documents:")
    for doc_comp in doc_comparisons[:5]:
        doc_id = doc_comp['doc_id']
        comparison = doc_comp['comparison']
        
        print(f"\n{doc_id}:")
        print(f"  Baseline entities: {doc_comp['baseline_count']}")
        print(f"  Canonical entities: {doc_comp['canonical_count']}")
        print(f"  In both systems: {len(comparison['in_both'])}")
        print(f"  Only baseline: {len(comparison['only_baseline'])}")
        print(f"  Only canonical: {len(comparison['only_canonical'])}")
        
        if comparison['only_baseline']:
            print(f"  Examples only in baseline:")
            for span, etype, start in list(comparison['only_baseline'])[:3]:
                print(f"    - '{span}' [{etype}] at pos {start}")
        
        if comparison['only_canonical']:
            print(f"  Examples only in canonical:")
            for span, etype, start in list(comparison['only_canonical'])[:3]:
                print(f"    - '{span}' [{etype}] at pos {start}")
    
    # Overall summary
    print("\n" + "="*60)
    print("OVERALL SUMMARY")
    print("="*60)
    
    total = total_both + total_only_baseline + total_only_canonical
    
    print(f"\nTotal entities:")
    print(f"  In both systems: {total_both} ({total_both/total*100:.1f}%)")
    print(f"  Only in baseline: {total_only_baseline} ({total_only_baseline/total*100:.1f}%)")
    print(f"  Only in canonical: {total_only_canonical} ({total_only_canonical/total*100:.1f}%)")
    print(f"  Total unique: {total}")
    
    print(f"\nAgreement metrics:")
    agreement_rate = total_both / total * 100 if total > 0 else 0
    print(f"  Agreement rate: {agreement_rate:.1f}%")
    
    baseline_total = total_both + total_only_baseline
    canonical_total = total_both + total_only_canonical
    
    if baseline_total > 0:
        baseline_recall = total_both / baseline_total * 100
        print(f"  Canonical recall (vs baseline): {baseline_recall:.1f}%")
    
    if canonical_total > 0:
        canonical_precision = total_both / canonical_total * 100
        print(f"  Canonical precision (vs baseline): {canonical_precision:.1f}%")
    
    print("\n" + "="*60)
    print("COMPARISON COMPLETE")
    print("="*60)
    
    # Save detailed comparison
    output_file = Path(__file__).parent.parent / "data" / "pipeline_comparison.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            'summary': {
                'total_both': total_both,
                'total_only_baseline': total_only_baseline,
                'total_only_canonical': total_only_canonical,
                'agreement_rate': agreement_rate
            },
            'entity_types': {
                'baseline': dict(baseline_types),
                'canonical': dict(canonical_types)
            },
            'documents': [{
                'doc_id': dc['doc_id'],
                'baseline_count': dc['baseline_count'],
                'canonical_count': dc['canonical_count'],
                'both_count': len(dc['comparison']['in_both']),
                'only_baseline_count': len(dc['comparison']['only_baseline']),
                'only_canonical_count': len(dc['comparison']['only_canonical'])
            } for dc in doc_comparisons]
        }, f, ensure_ascii=False, indent=2)
    
    print(f"\n[SAVED] Detailed comparison saved to: {output_file}")


if __name__ == "__main__":
    main()
