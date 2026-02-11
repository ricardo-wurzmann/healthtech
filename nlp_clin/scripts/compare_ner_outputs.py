"""
Compare old NER (lexicons/*.txt) vs new NER (canonical) outputs.
"""
import json
from pathlib import Path
from typing import List, Dict
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from ner_canonical_loader import CanonicalLexiconLoader


def compare_on_text(text: str, old_results: List, new_results: List) -> Dict:
    """
    Compare NER results from both systems on the same text.
    
    Returns:
        {
            "text": input text,
            "old_count": number of entities found by old system,
            "new_count": number of entities found by new system,
            "only_in_old": entities only found by old system,
            "only_in_new": entities only found by new system,
            "in_both": entities found by both systems
        }
    """
    # For now, just return new results since we don't have old system integrated
    return {
        "text": text,
        "old_count": 0,  # Would be len(old_results) when baseline_ner is integrated
        "new_count": len(new_results),
        "only_in_old": [],
        "only_in_new": new_results,
        "in_both": []
    }


def run_comparison(test_cases_file: str):
    """
    Run comparison on multiple test cases.
    
    Args:
        test_cases_file: Path to JSON file with test cases
    """
    # Load test cases
    test_cases_path = Path(test_cases_file)
    if not test_cases_path.exists():
        print(f"ERROR: Test cases file not found: {test_cases_file}")
        return
    
    with open(test_cases_path, encoding='utf-8') as f:
        test_cases = json.load(f)
    
    # Initialize new system
    print("="*60)
    print("INITIALIZING CANONICAL NER SYSTEM")
    print("="*60)
    loader = CanonicalLexiconLoader(canonical_version="v1_1")
    loader.load()
    
    # Show statistics
    stats = loader.get_stats()
    print("\n" + "="*60)
    print("LOADER STATISTICS")
    print("="*60)
    for key, value in stats.items():
        if isinstance(value, dict):
            print(f"{key}:")
            for sub_key, sub_value in value.items():
                print(f"  {sub_key}: {sub_value}")
        else:
            print(f"{key}: {value}")
    
    results = []
    
    for i, test_case in enumerate(test_cases, 1):
        text = test_case['text']
        
        print(f"\n{'='*60}")
        print(f"Test Case {i}: {test_case.get('description', 'No description')}")
        print(f"{'='*60}")
        print(f"Text: {text}")
        
        # Run new NER
        new_matches = loader.match_text(text)
        
        print(f"\nNew NER Results: {len(new_matches)} entities")
        
        # Group by entity type
        by_type = {}
        for match in new_matches:
            entity_type = match['entity_type']
            if entity_type not in by_type:
                by_type[entity_type] = []
            by_type[entity_type].append(match)
        
        # Show results grouped by type
        for entity_type, matches in sorted(by_type.items()):
            print(f"\n  {entity_type} ({len(matches)}):")
            for match in matches:
                print(f"    - '{match['text']}' -> {match['concept_name'][:60]}")
                print(f"      [{match['vocabulary']}:{match['concept_id']}, "
                      f"{match['entry_type']}, conf={match['confidence']:.2f}, "
                      f"policy={match['match_policy']}]")
        
        if len(new_matches) == 0:
            print("  (No entities detected)")
        
        results.append({
            "case_id": i,
            "description": test_case.get('description'),
            "text": text,
            "text_length": len(text),
            "new_count": len(new_matches),
            "new_entities": new_matches
        })
    
    # Save results
    output_dir = Path(__file__).parent.parent / "data"
    output_file = output_dir / "ner_comparison_results.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"\n{'='*60}")
    print(f"COMPARISON COMPLETE")
    print(f"{'='*60}")
    print(f"Results saved to {output_file}")
    
    # Summary statistics
    total_entities = sum(r['new_count'] for r in results)
    print(f"\nSummary:")
    print(f"  Total test cases: {len(results)}")
    print(f"  Total entities detected: {total_entities}")
    print(f"  Average per case: {total_entities / len(results):.1f}")
    
    return results


if __name__ == "__main__":
    # Default test cases file
    test_cases_file = Path(__file__).parent.parent / "data" / "test_cases" / "ner_examples.json"
    
    if not test_cases_file.exists():
        print(f"WARNING: Test cases file not found: {test_cases_file}")
        print("Please create test cases first")
        sys.exit(1)
    
    run_comparison(str(test_cases_file))
