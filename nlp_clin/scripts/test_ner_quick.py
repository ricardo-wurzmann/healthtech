"""
Quick test of NER on first 10 real clinical cases from pepv1.json
"""
import json
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from ner_canonical_loader import CanonicalLexiconLoader

def main():
    print("="*60)
    print("QUICK NER TEST ON FIRST 10 CASES")
    print("="*60)
    
    # Load NER system
    print("\n[1/4] Loading NER system...")
    loader = CanonicalLexiconLoader(canonical_version="v1_1")
    loader.load()
    print("[OK] NER system loaded")
    
    # Load data
    print("\n[2/4] Loading pepv1.json...")
    pepv1_path = Path(__file__).parent.parent / "data" / "raw" / "pepv1.json"
    with open(pepv1_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    print(f"[OK] Loaded {len(data)} total cases")
    
    # Test on first 10
    print("\n[3/4] Running NER on first 10 cases...")
    test_cases = data[:10]
    total_entities = 0
    
    for i, case in enumerate(test_cases, 1):
        text = case['raw_text']
        entities = loader.match_text(text)
        total_entities += len(entities)
        print(f"  Case {case['case_id']:2d}: {len(entities):3d} entities - text length: {len(text):4d} chars")
    
    print(f"\n[OK] Processed {len(test_cases)} cases")
    print(f"[STATS] Total entities: {total_entities}")
    print(f"[STATS] Average per case: {total_entities/len(test_cases):.1f}")
    
    # Show one example
    print("\n[4/4] Example from first case:")
    first_case = test_cases[0]
    entities = loader.match_text(first_case['raw_text'])
    
    print(f"\nCase {first_case['case_id']}: {len(entities)} entities found")
    print(f"Text preview: {first_case['raw_text'][:150]}...")
    
    if entities:
        print("\nFirst 10 entities:")
        for ent in entities[:10]:
            print(f"  - '{ent['text']}' [{ent['entity_type']}] "
                  f"conf={ent['confidence']:.2f} ({ent['vocabulary']})")
    
    print("\n" + "="*60)
    print("[COMPLETE] Quick test finished successfully!")
    print("="*60)

if __name__ == "__main__":
    main()
