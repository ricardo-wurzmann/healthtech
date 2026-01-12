"""
Comprehensive test script to verify lexicon loading, indexing, and usage.
"""
from pathlib import Path
import sys

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.lexicon import LEXICON, load_all_lexicons
from src.baseline_ner import extract_entities_baseline, _index
from src.segment import split_sentences
from src.context import classify_assertion

print("=" * 80)
print("COMPREHENSIVE LEXICON VERIFICATION")
print("=" * 80)

# 1. Check lexicon loading
print("\n1. LEXICON LOADING")
print("-" * 80)
print(f"Total entries loaded: {len(LEXICON)}")

types = {}
for term, etype in LEXICON:
    types[etype] = types.get(etype, 0) + 1

print(f"Entity types distribution:")
for etype, count in sorted(types.items()):
    print(f"  {etype}: {count} entries")

# Check for each expected type
expected_types = {"SYMPTOM", "ANATOMY", "PROCEDURE", "TEST", "DRUG"}
missing_types = expected_types - set(types.keys())
if missing_types:
    print(f"  ⚠ Missing types: {missing_types}")
else:
    print(f"  ✓ All expected types present")

# 2. Check indexing
print("\n2. INDEXING VERIFICATION")
print("-" * 80)
print(f"Index entries: {len(_index.entries)}")
print(f"Single-token entries: {len(_index.single_token_entries)}")
print(f"Multi-token entries: {len(_index.multi_token_entries)}")
print(f"Token index size: {len(_index.token_to_entries)}")

# Sample some entries
print(f"\nSample indexed entries:")
for i, entry in enumerate(_index.entries[:5]):
    print(f"  {i+1}. '{entry.original_term}' -> {entry.entity_type} (normalized: '{entry.normalized_term}')")

# 3. Test matching with sample sentences
print("\n3. MATCHING VERIFICATION")
print("-" * 80)

test_cases = [
    {
        "text": "Paciente apresenta febre alta e cefaleia intensa.",
        "expected": ["febre", "cefaleia"],
        "type": "SYMPTOM"
    },
    {
        "text": "Foi realizado hemograma e tomografia do abdome.",
        "expected": ["hemograma", "tomografia", "abdome"],
        "type": "MIXED"
    },
    {
        "text": "Prescrito paracetamol e dipirona para dor.",
        "expected": ["paracetamol", "dipirona", "dor"],
        "type": "MIXED"
    },
    {
        "text": "Paciente refere dor abdominal no epigástrio.",
        "expected": ["dor abdominal", "epigástrio"],
        "type": "MIXED"
    },
    {
        "text": "Realizado FAST para avaliação de trauma.",
        "expected": ["FAST"],
        "type": "PROCEDURE"
    },
    {
        "text": "Paciente com dispneia e taquicardia.",
        "expected": ["dispneia", "taquicardia"],
        "type": "SYMPTOM"
    },
    {
        "text": "Exame de urina tipo 1 e glicemia capilar.",
        "expected": ["urina tipo 1", "glicemia capilar"],
        "type": "TEST"
    },
]

for i, case in enumerate(test_cases, 1):
    print(f"\nTest {i}: {case['text']}")
    sentences = split_sentences(case['text'])
    sentence_tuples = [(s.text, s.start, s.end) for s in sentences]
    entities = extract_entities_baseline(case['text'], sentence_tuples)
    
    if entities:
        detected = [e.span.lower() for e in entities]
        print(f"  Detected: {detected}")
        for e in entities:
            assertion = classify_assertion(case['text'])
            print(f"    → '{e.span}' [{e.type}] (score: {e.score:.2f}, assertion: {assertion})")
        
        # Check if expected terms were found
        found_expected = []
        for exp in case['expected']:
            exp_lower = exp.lower()
            if any(exp_lower in d or d in exp_lower for d in detected):
                found_expected.append(exp)
        
        if len(found_expected) == len(case['expected']):
            print(f"  ✓ All expected terms found")
        else:
            missing = set(case['expected']) - set(found_expected)
            print(f"  ⚠ Missing expected terms: {missing}")
    else:
        print(f"  ✗ No entities detected")

# 4. Check priority for symptoms
print("\n4. SYMPTOM PRIORITY VERIFICATION")
print("-" * 80)

# Check if core symptoms are loaded before expanded
core_terms = set()
expanded_terms = set()

# Load separately to check
lexicon_dir = Path("data/lexicons")
if (lexicon_dir / "symptoms_core_ptbr.txt").exists():
    with open(lexicon_dir / "symptoms_core_ptbr.txt", 'r', encoding='utf-8') as f:
        core_terms = {line.strip().lower() for line in f if line.strip()}
    print(f"Core symptoms file: {len(core_terms)} entries")

if (lexicon_dir / "symptoms_expanded_ptbr.txt").exists():
    with open(lexicon_dir / "symptoms_expanded_ptbr.txt", 'r', encoding='utf-8') as f:
        expanded_terms = {line.strip().lower() for line in f if line.strip()}
    print(f"Expanded symptoms file: {len(expanded_terms)} entries")

# Check overlap
overlap = core_terms & expanded_terms
print(f"Overlapping terms: {len(overlap)}")

# Check if loaded lexicon has core terms prioritized
loaded_symptoms = {term.lower() for term, etype in LEXICON if etype == "SYMPTOM"}
core_in_loaded = core_terms & loaded_symptoms
print(f"Core symptoms in loaded lexicon: {len(core_in_loaded)}/{len(core_terms)}")

if len(core_in_loaded) == len(core_terms):
    print("  ✓ All core symptoms loaded")
else:
    missing_core = core_terms - core_in_loaded
    print(f"  ⚠ Missing core symptoms: {len(missing_core)}")

print("\n" + "=" * 80)
print("VERIFICATION COMPLETE")
print("=" * 80)

