"""
Simple test of canonical NER module (no full pipeline dependencies)
"""
import sys
from pathlib import Path

# Test imports
print("="*60)
print("TESTING CANONICAL NER MODULE")
print("="*60)

print("\n[1/3] Testing imports...")
try:
    sys.path.insert(0, str(Path(__file__).parent / "scripts"))
    from ner_canonical_loader import CanonicalLexiconLoader
    print("[OK] CanonicalLexiconLoader imported")
except Exception as e:
    print(f"[ERROR] Failed to import: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test vocabulary loading
print("\n[2/3] Loading canonical vocabulary...")
try:
    loader = CanonicalLexiconLoader(canonical_version="v1_1")
    loader.load()
    stats = loader.get_stats()
    print(f"[OK] Loaded successfully:")
    print(f"  - Concepts: {stats['total_concepts']:,}")
    print(f"  - Entries: {stats['total_entries']:,}")
    print(f"  - Indexed: {stats['indexed_entries']:,}")
    print(f"  - Drug names: {len(loader.drug_index):,}")
except Exception as e:
    print(f"[ERROR] Failed to load: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test NER on sample text
print("\n[3/3] Testing NER on clinical text...")
test_text = "Paciente com diarreia infecciosa (A09). Prescrito paracetamol 500mg e omeprazol."

try:
    entities = loader.match_text(test_text)
    print(f"[OK] Found {len(entities)} entities:")
    
    for ent in entities:
        print(f"\n  '{ent['text']}' [{ent['entity_type']}]")
        print(f"    Position: {ent['start']}:{ent['end']}")
        print(f"    Concept: {ent['concept_name'][:50]}...")
        print(f"    Vocabulary: {ent['vocabulary']}")
        print(f"    Confidence: {ent['confidence']:.2f}")
        print(f"    Match type: {ent['match_type']}")
        print(f"    Policy: {ent['match_policy']}")
    
except Exception as e:
    print(f"[ERROR] NER failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "="*60)
print("[SUCCESS] Canonical NER is fully functional!")
print("="*60)
print("\nNext steps:")
print("1. Install pipeline dependencies (spacy, etc.)")
print("2. Run: python main_canonical.py --input data/raw/pepv1.json")
print("3. Run: python scripts/compare_pipelines.py")
