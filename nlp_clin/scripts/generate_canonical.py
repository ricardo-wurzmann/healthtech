import csv
import hashlib
import logging
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path


# Version configuration
CANONICAL_VERSION = "v1.1"

BASE_DIR = Path(__file__).resolve().parents[1]
STAGING_DIR = BASE_DIR / "data" / "vocab" / "staging"
CANONICAL_DIR = BASE_DIR / "data" / "vocab" / f"canonical_{CANONICAL_VERSION.replace('.', '_')}"

LOG = logging.getLogger("generate_canonical")


def read_csv(path: Path):
    if not path.exists():
        LOG.warning("Missing staging file: %s", path)
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def stable_hash(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:12]


def normalize_text(value: str) -> str:
    return " ".join((value or "").split())


def compute_file_hash(path: Path) -> str:
    """Compute MD5 hash of a file."""
    if not path.exists():
        return ""
    md5 = hashlib.md5()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            md5.update(chunk)
    return md5.hexdigest()


def count_csv_rows(path: Path) -> int:
    """Count rows in a CSV file (excluding header)."""
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8", newline="") as f:
        return sum(1 for _ in csv.DictReader(f))


def add_concept(concepts, concept_id, concept_name, entity_type, domain, vocabulary, source_file, version):
    concepts[concept_id] = {
        "concept_id": concept_id,
        "concept_name": concept_name,
        "entity_type": entity_type,
        "domain": domain,
        "vocabulary": vocabulary,
        "source_file": source_file,
        "version": version,
        "language": "pt-BR",
        "status": "active",
    }


def add_entry(entries, entry_text, concept_id, entry_type, match_policy, source_file):
    entry_text = normalize_text(entry_text)
    if not entry_text:
        return
    key = (entry_text, concept_id, entry_type, match_policy, source_file)
    if key in entries:
        return
    entries.add(key)


def build_labs_ids(rows):
    # Use raw_unit as it contains the actual test name, raw_exam_name contains codes
    names = sorted({normalize_text(row["raw_unit"]) for row in rows if row.get("raw_unit")})
    return {name: f"LAB_{idx:06d}" for idx, name in enumerate(names, start=1)}


def load_siglario():
    allowed = read_csv(STAGING_DIR / "siglario_allowed_raw.csv")
    ambiguous = read_csv(STAGING_DIR / "siglario_ambiguous_raw.csv")
    institutional = read_csv(STAGING_DIR / "siglario_institucional_raw.csv")
    prohibited = read_csv(STAGING_DIR / "siglario_prohibited_raw.csv")
    return allowed, ambiguous, institutional, prohibited


def build_metadata_yaml(payload: dict, indent: int = 0) -> str:
    """Build YAML from nested dictionary structure."""
    lines = []
    prefix = "  " * indent
    
    for key, value in payload.items():
        if isinstance(value, dict):
            lines.append(f"{prefix}{key}:")
            lines.append(build_metadata_yaml(value, indent + 1).rstrip())
        elif isinstance(value, list):
            lines.append(f"{prefix}{key}:")
            for item in value:
                if isinstance(item, dict):
                    lines.append(f"{prefix}  -")
                    for sub_key, sub_value in item.items():
                        lines.append(f"{prefix}    {sub_key}: {sub_value}")
                else:
                    lines.append(f"{prefix}  - {item}")
        else:
            # Handle strings with special characters
            if isinstance(value, str) and ("\n" in value or ":" in value):
                lines.append(f"{prefix}{key}: '{value}'")
            else:
                lines.append(f"{prefix}{key}: {value}")
    
    return "\n".join(lines) + ("\n" if indent == 0 else "")


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
    CANONICAL_DIR.mkdir(parents=True, exist_ok=True)

    concepts = {}
    entries = set()
    blocked_terms = []
    ambiguity_rows = []
    entry_type_counts = Counter()
    vocab_counts = Counter()

    # CID-10
    cid10_rows = read_csv(STAGING_DIR / "cid10_raw.csv")
    for row in cid10_rows:
        code = normalize_text(row.get("raw_code"))
        name = normalize_text(row.get("raw_name"))
        if not code or not name:
            continue
        add_concept(
            concepts,
            code,
            name,
            "PROBLEM",
            "problem",
            "CID10",
            row.get("source", "cid10_raw.csv"),
            row.get("version", ""),
        )
        add_entry(entries, name, code, "official", "safe_exact", row.get("source", "cid10_raw.csv"))
        add_entry(entries, code, code, "code", "safe_exact", row.get("source", "cid10_raw.csv"))
        entry_type_counts["official"] += 1
        entry_type_counts["code"] += 1
        vocab_counts["CID10"] += 1

    # TUSS Procedures
    proc_rows = read_csv(STAGING_DIR / "tuss_proc_raw.csv")
    for row in proc_rows:
        code = normalize_text(row.get("raw_code"))
        term = normalize_text(row.get("raw_term"))
        if not code or not term:
            continue
        add_concept(
            concepts,
            code,
            term,
            "PROCEDURE",
            "procedure",
            "TUSS_PROC",
            row.get("source", "tuss_proc_raw.csv"),
            row.get("version", ""),
        )
        add_entry(entries, term, code, "official", "safe_exact", row.get("source", "tuss_proc_raw.csv"))
        add_entry(entries, code, code, "code", "safe_exact", row.get("source", "tuss_proc_raw.csv"))
        entry_type_counts["official"] += 1
        entry_type_counts["code"] += 1
        vocab_counts["TUSS_PROC"] += 1

    # TUSS Drugs
    drug_rows = read_csv(STAGING_DIR / "tuss_drugs_raw.csv")
    for row in drug_rows:
        code = normalize_text(row.get("raw_code"))
        name = normalize_text(row.get("raw_name"))
        if not code or not name:
            continue
        add_concept(
            concepts,
            code,
            name,
            "DRUG",
            "drug",
            "TUSS_DRUG",
            row.get("source", "tuss_drugs_raw.csv"),
            row.get("version", ""),
        )
        add_entry(entries, name, code, "official", "safe_exact", row.get("source", "tuss_drugs_raw.csv"))
        add_entry(entries, code, code, "code", "safe_exact", row.get("source", "tuss_drugs_raw.csv"))
        entry_type_counts["official"] += 1
        entry_type_counts["code"] += 1
        vocab_counts["TUSS_DRUG"] += 1

    # Labs
    lab_rows = read_csv(STAGING_DIR / "labs_raw.csv")
    lab_ids = build_labs_ids(lab_rows)
    for row in lab_rows:
        # Use raw_unit as it contains the actual test name, raw_exam_name contains codes
        name = normalize_text(row.get("raw_unit"))
        if not name:
            continue
        concept_id = lab_ids[name]
        add_concept(
            concepts,
            concept_id,
            name,
            "TEST",
            "measurement",
            "LABS",
            row.get("source", "labs_raw.csv"),
            row.get("version", ""),
        )
        add_entry(entries, name, concept_id, "official", "safe_exact", row.get("source", "labs_raw.csv"))
        entry_type_counts["official"] += 1
        vocab_counts["LABS"] += 1

    # Siglario
    allowed, ambiguous, institutional, prohibited = load_siglario()
    sigla_source = "siglario_allowed_raw.csv"

    context_map = {}
    for row in ambiguous:
        abbr = normalize_text(row.get("abbreviation"))
        context = normalize_text(row.get("context_required"))
        meaning_1 = normalize_text(row.get("meaning_1"))
        meaning_2 = normalize_text(row.get("meaning_2"))
        if not abbr:
            continue
        context_map[abbr] = context or "Use context to disambiguate"
        for meaning in [meaning_1, meaning_2]:
            if meaning:
                key = f"{abbr}|{meaning}"
                context_map.setdefault(key, context_map[abbr])

    sigla_rows = []
    for row in allowed:
        sigla_rows.append(
            (
                normalize_text(row.get("abbreviation")),
                normalize_text(row.get("meaning")),
                row.get("source", sigla_source),
                row.get("version", ""),
            )
        )
    for row in institutional:
        sigla_rows.append(
            (
                normalize_text(row.get("abbreviation")),
                normalize_text(row.get("meaning")),
                row.get("source", "siglario_institucional_raw.csv"),
                row.get("version", ""),
            )
        )
    for row in ambiguous:
        abbr = normalize_text(row.get("abbreviation"))
        meaning_1 = normalize_text(row.get("meaning_1"))
        meaning_2 = normalize_text(row.get("meaning_2"))
        source = row.get("source", "siglario_ambiguous_raw.csv")
        version = row.get("version", "")
        if abbr and meaning_1:
            sigla_rows.append((abbr, meaning_1, source, version))
        if abbr and meaning_2:
            sigla_rows.append((abbr, meaning_2, source, version))

    sigla_map = defaultdict(set)
    for abbr, meaning, _, _ in sigla_rows:
        if abbr and meaning:
            sigla_map[abbr].add(meaning)

    # Track ambiguous abbreviations with their concept IDs
    ambiguous_abbrevs = defaultdict(lambda: {"concept_ids": [], "source_files": set()})
    
    for abbr, meaning, source_file, version in sigla_rows:
        if not abbr or not meaning:
            continue
        meanings = sigla_map[abbr]
        is_ambiguous = len(meanings) > 1
        # Abbreviation entry policy: context_required if ambiguous, safe_exact otherwise
        abbr_match_policy = "context_required" if is_ambiguous else "safe_exact"
        # Official meaning entry policy: always safe_exact
        meaning_match_policy = "safe_exact"
        
        concept_id = stable_hash(f"{abbr}|{meaning}")
        add_concept(
            concepts,
            concept_id,
            meaning,
            "ABBREV",
            "abbrev",
            "SIGLARIO",
            source_file,
            version,
        )
        add_entry(entries, abbr, concept_id, "abbr", abbr_match_policy, source_file)
        add_entry(entries, meaning, concept_id, "official", meaning_match_policy, source_file)
        entry_type_counts["abbr"] += 1
        entry_type_counts["official"] += 1
        vocab_counts["SIGLARIO"] += 1

        if is_ambiguous:
            ambiguous_abbrevs[abbr]["concept_ids"].append(concept_id)
            ambiguous_abbrevs[abbr]["source_files"].add(source_file)
    
    # Generate deduplicated ambiguity rows (one per abbreviation)
    for abbr, data in ambiguous_abbrevs.items():
        meanings = sigla_map[abbr]
        possible_meanings = "; ".join(sorted(meanings))
        context_rule = context_map.get(abbr, "Use context to disambiguate")
        # Use the first concept_id for reference
        concept_id = data["concept_ids"][0] if data["concept_ids"] else ""
        source_files = ", ".join(sorted(data["source_files"]))
        ambiguity_rows.append(
            {
                "entry_text": abbr,
                "concept_id": concept_id,
                "conflict_type": "multiple_meanings",
                "possible_meanings": possible_meanings,
                "context_rule": context_rule,
                "source_file": source_files,
            }
        )

    # Blocked terms
    for row in prohibited:
        abbr = normalize_text(row.get("abbreviation"))
        reason = normalize_text(row.get("danger_reason")) or normalize_text(row.get("incorrect_meaning"))
        if not abbr:
            continue
        blocked_terms.append(
            {
                "term": abbr,
                "reason": reason or "prohibited abbreviation",
                "source_file": row.get("source", "siglario_prohibited_raw.csv"),
            }
        )

    # Write outputs
    concepts_rows = list(concepts.values())
    entries_rows = [
        {
            "entry_text": entry_text,
            "concept_id": concept_id,
            "entry_type": entry_type,
            "match_policy": match_policy,
            "source_file": source_file,
            "language": "pt-BR",
        }
        for (entry_text, concept_id, entry_type, match_policy, source_file) in entries
    ]
    write_csv(
        CANONICAL_DIR / "concepts.csv",
        [
            "concept_id",
            "concept_name",
            "entity_type",
            "domain",
            "vocabulary",
            "source_file",
            "version",
            "language",
            "status",
        ],
        sorted(concepts_rows, key=lambda x: x["concept_id"]),
    )
    write_csv(
        CANONICAL_DIR / "entries.csv",
        ["entry_text", "concept_id", "entry_type", "match_policy", "source_file", "language"],
        sorted(entries_rows, key=lambda x: (x["entry_text"], x["concept_id"])),
    )
    write_csv(
        CANONICAL_DIR / "blocked_terms.csv",
        ["term", "reason", "source_file"],
        blocked_terms,
    )
    write_csv(
        CANONICAL_DIR / "ambiguity.csv",
        ["entry_text", "concept_id", "conflict_type", "possible_meanings", "context_rule", "source_file"],
        ambiguity_rows,
    )

    # Collect source file metadata
    source_files = [
        "cid10_raw.csv",
        "tuss_proc_raw.csv",
        "tuss_drugs_raw.csv",
        "labs_raw.csv",
        "siglario_allowed_raw.csv",
        "siglario_ambiguous_raw.csv",
        "siglario_institucional_raw.csv",
        "siglario_prohibited_raw.csv",
    ]
    sources_metadata = []
    for filename in source_files:
        filepath = STAGING_DIR / filename
        if filepath.exists():
            sources_metadata.append({
                "file": filename,
                "rows": count_csv_rows(filepath),
                "hash": compute_file_hash(filepath),
            })
    
    # Compute output file hashes
    output_files = {
        "concepts_csv": CANONICAL_DIR / "concepts.csv",
        "entries_csv": CANONICAL_DIR / "entries.csv",
        "blocked_terms_csv": CANONICAL_DIR / "blocked_terms.csv",
        "ambiguity_csv": CANONICAL_DIR / "ambiguity.csv",
    }
    file_hashes = {key: compute_file_hash(path) for key, path in output_files.items()}
    
    # Build comprehensive metadata
    counts = {
        "total_concepts": len(concepts_rows),
        "total_entries": len(entries_rows),
        "blocked_terms": len(blocked_terms),
        "ambiguity": len(ambiguity_rows),
    }
    
    # Compute match policy distribution
    policy_counter = Counter()
    for entry_text, concept_id, entry_type, match_policy, source_file in entries:
        policy_counter[match_policy] += 1
    
    metadata = {
        "version": CANONICAL_VERSION,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "generated_by": "scripts/generate_canonical.py",
        "counts": {
            **counts,
            "by_vocabulary": dict(vocab_counts),
        },
        "entry_types": dict(entry_type_counts),
        "match_policies": {
            "safe_exact": {
                "description": "Exact string match only, no fuzzy matching allowed",
                "applies_to": ["CID10", "TUSS_PROC", "TUSS_DRUG", "LABS", "SIGLARIO (non-ambiguous)"],
                "rationale": "Medical terminology requires precision to avoid errors",
                "count": policy_counter.get("safe_exact", 0),
            },
            "context_required": {
                "description": "Match requires clinical context for disambiguation",
                "applies_to": ["SIGLARIO (ambiguous only)"],
                "rationale": "Ambiguous abbreviations need surrounding context",
                "examples": ["ADA: ADENOSINA DEAMINASE vs AMPLITUDE DE ACOMODACAO", "CA: cancer marker vs cancer"],
                "count": policy_counter.get("context_required", 0),
            },
            "blocked": {
                "description": "Terms explicitly blocked from matching",
                "applies_to": [],
                "rationale": "Reserved for prohibited terms",
                "count": policy_counter.get("blocked", 0),
            },
        },
        "sources": sources_metadata,
        "file_hashes": file_hashes,
        "notes": "v1.1: Added strict match_policy rules based on vocabulary type",
    }
    
    # Compute metadata hash
    metadata_hash = hashlib.sha256(str(metadata).encode("utf-8")).hexdigest()[:16]
    
    # Write metadata
    metadata_path = CANONICAL_DIR / "metadata.yaml"
    metadata_path.write_text(build_metadata_yaml(metadata), encoding="utf-8")

    # Validate match policies
    LOG.info("")
    LOG.info("Match Policy Distribution:")
    for policy, count in sorted(policy_counter.items()):
        LOG.info("  %s: %s", policy, count)
    
    # Validate ambiguous abbreviations have context_required
    ambig_abbrs_set = set(ambiguous_abbrevs.keys())
    context_required_abbrs = set()
    for entry_text, concept_id, entry_type, match_policy, source_file in entries:
        if entry_type == "abbr" and match_policy == "context_required":
            context_required_abbrs.add(entry_text)
    
    # Check that all ambiguous abbrs have context_required
    missing_context = ambig_abbrs_set - context_required_abbrs
    if missing_context:
        LOG.warning("WARNING: %s ambiguous abbrs don't have context_required policy", len(missing_context))
        LOG.warning("  Examples: %s", list(missing_context)[:5])
    else:
        LOG.info("All ambiguous abbreviations correctly flagged with context_required")
    
    # Summary
    LOG.info("")
    LOG.info("=" * 60)
    LOG.info("Canonical %s frozen at %s", CANONICAL_VERSION, CANONICAL_DIR)
    LOG.info("Total: %s concepts, %s entries", counts["total_concepts"], counts["total_entries"])
    LOG.info("Vocabulary breakdown: %s", dict(vocab_counts))
    LOG.info("Metadata hash: %s", metadata_hash)
    LOG.info("=" * 60)


if __name__ == "__main__":
    main()
