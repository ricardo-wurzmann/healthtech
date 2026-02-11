"""
Quick test of canonical pipeline on one case
"""
import sys
from pathlib import Path

# Test imports
print("Testing imports...")
try:
    from src.canonical_ner import extract_entities_canonical, get_canonical_loader
    print("[OK] canonical_ner imported")
except Exception as e:
    print(f"[ERROR] Failed to import canonical_ner: {e}")
    sys.exit(1)

try:
    from src.segment import split_sentences
    print("[OK] segment imported")
except Exception as e:
    print(f"[ERROR] Failed to import segment: {e}")
    sys.exit(1)

# Test vocabulary loading
print("\nTesting vocabulary loading...")
try:
    loader = get_canonical_loader()
    stats = loader.get_stats()
    print(f"[OK] Loaded {stats['total_concepts']} concepts")
except Exception as e:
    print(f"[ERROR] Failed to load vocabulary: {e}")
    sys.exit(1)

# Test NER on sample text
print("\nTesting NER on sample text...")
test_text = "Paciente com diarreia infecciosa. Prescrito paracetamol 500mg."

try:
    sents = split_sentences(test_text)
    sentences = [(s.text, s.start, s.end) for s in sents]
    print(f"[OK] Split into {len(sentences)} sentences")
    
    entities = extract_entities_canonical(test_text, sentences)
    print(f"[OK] Found {len(entities)} entities")
    
    for ent in entities:
        print(f"  - '{ent.span}' [{ent.type}] conf={ent.score:.2f}")
        if isinstance(ent.evidence, dict):
            print(f"    vocab: {ent.evidence.get('vocabulary')}, "
                  f"concept: {ent.evidence.get('concept_id')}")
    
except Exception as e:
    print(f"[ERROR] NER failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "="*60)
print("[SUCCESS] Canonical pipeline is working!")
print("="*60)
