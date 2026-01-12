"""
Generate LEXICON_COUNTS.json with detailed lexicon loading statistics.
"""
from __future__ import annotations
import json
from pathlib import Path
from collections import defaultdict

try:
    from unidecode import unidecode
except ImportError:
    # Fallback if unidecode is not installed
    def unidecode(s: str) -> str:
        return s.encode("ascii", "ignore").decode("ascii")

LEXICON_FILES = [
    ("symptoms_core_ptbr.txt", "SYMPTOM", 1),
    ("symptoms_expanded_ptbr.txt", "SYMPTOM", 2),
    ("anatomy_ptbr.txt", "ANATOMY", 1),
    ("procedures_ptbr.txt", "PROCEDURE", 1),
    ("tests_exams_ptbr.txt", "TEST", 1),
    ("drugs_ptbr.txt", "DRUG", 1),
]


def load_lexicon_file(filepath: Path) -> list[str]:
    """Load a lexicon file and return list of terms."""
    if not filepath.exists():
        return []
    
    terms = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            term = line.strip()
            if term:
                terms.append(term)
    return terms


def normalize_for_dedup(term: str) -> str:
    """Normalize term for duplicate detection."""
    return unidecode(term.lower().strip())


def generate_lexicon_counts(lexicon_dir: Path) -> dict:
    """Generate comprehensive lexicon counts."""
    results = {
        "files": {},
        "loaded": {},
        "deduplication": {},
        "summary": {}
    }
    
    # Load all files
    all_entries_by_file = {}
    all_entries_normalized = {}
    
    for filename, entity_type, priority in LEXICON_FILES:
        filepath = lexicon_dir / filename
        terms = load_lexicon_file(filepath)
        
        # File-level stats
        results["files"][filename] = {
            "path": str(filepath),
            "exists": filepath.exists(),
            "entity_type": entity_type,
            "priority": priority,
            "raw_count": len(terms),
            "unique_in_file": len(set(terms)),
            "sample_entries": terms[:5] if terms else []
        }
        
        all_entries_by_file[filename] = terms
        
        # Track normalized terms for deduplication
        normalized_terms = {}
        for term in terms:
            norm = normalize_for_dedup(term)
            if norm not in normalized_terms:
                normalized_terms[norm] = term  # Keep original
            all_entries_normalized[norm] = {
                "original": term,
                "source_file": filename,
                "entity_type": entity_type,
                "priority": priority
            }
    
    # Simulate loading with priority (core symptoms first)
    loaded_entries = []
    seen_normalized = set()
    loaded_by_file = defaultdict(list)
    dedup_stats = defaultdict(lambda: {"kept": 0, "skipped": 0})
    
    # Sort by priority
    sorted_files = sorted(LEXICON_FILES, key=lambda x: x[2])
    
    for filename, entity_type, priority in sorted_files:
        terms = all_entries_by_file.get(filename, [])
        for term in terms:
            norm = normalize_for_dedup(term)
            if norm not in seen_normalized:
                seen_normalized.add(norm)
                loaded_entries.append((term, entity_type))
                loaded_by_file[filename].append(term)
                dedup_stats[filename]["kept"] += 1
            else:
                # Check if we're overriding a lower priority entry
                existing = all_entries_normalized[norm]
                if priority < existing["priority"]:
                    # This shouldn't happen in our priority order, but log it
                    dedup_stats[filename]["kept"] += 1
                    dedup_stats[existing["source_file"]]["skipped"] += 1
                else:
                    dedup_stats[filename]["skipped"] += 1
    
    # Generate loaded stats
    loaded_by_type = defaultdict(int)
    for term, etype in loaded_entries:
        loaded_by_type[etype] += 1
    
    for filename, entity_type, priority in LEXICON_FILES:
        results["loaded"][filename] = {
            "entity_type": entity_type,
            "entries_loaded": len(loaded_by_file[filename]),
            "sample_loaded": loaded_by_file[filename][:5] if loaded_by_file[filename] else []
        }
    
    # Deduplication stats
    for filename in all_entries_by_file:
        results["deduplication"][filename] = dedup_stats[filename]
    
    # Summary
    results["summary"] = {
        "total_files": len(LEXICON_FILES),
        "total_raw_entries": sum(len(terms) for terms in all_entries_by_file.values()),
        "total_loaded_entries": len(loaded_entries),
        "deduplication_rate": 1.0 - (len(loaded_entries) / sum(len(terms) for terms in all_entries_by_file.values())) if sum(len(terms) for terms in all_entries_by_file.values()) > 0 else 0.0,
        "entries_by_type": dict(loaded_by_type),
        "files_by_type": {}
    }
    
    # Files by type
    for filename, entity_type, _ in LEXICON_FILES:
        if entity_type not in results["summary"]["files_by_type"]:
            results["summary"]["files_by_type"][entity_type] = []
        results["summary"]["files_by_type"][entity_type].append(filename)
    
    return results


if __name__ == "__main__":
    # Get lexicon directory
    script_dir = Path(__file__).parent
    lexicon_dir = script_dir.parent / "data" / "lexicons"
    
    counts = generate_lexicon_counts(lexicon_dir)
    
    # Save to JSON
    output_path = script_dir / "LEXICON_COUNTS.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(counts, f, indent=2, ensure_ascii=False)
    
    print(f"Generated {output_path}")
    print(f"\nSummary:")
    print(f"  Total files: {counts['summary']['total_files']}")
    print(f"  Total raw entries: {counts['summary']['total_raw_entries']}")
    print(f"  Total loaded entries: {counts['summary']['total_loaded_entries']}")
    print(f"  Deduplication rate: {counts['summary']['deduplication_rate']:.2%}")
    print(f"\nEntries by type:")
    for etype, count in sorted(counts['summary']['entries_by_type'].items()):
        print(f"  {etype}: {count}")

