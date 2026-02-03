import csv
import hashlib
import logging
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
STAGING_DIR = BASE_DIR / "nlp_clin" / "data" / "vocab" / "staging"
CANONICAL_DIR = BASE_DIR / "nlp_clin" / "data" / "vocab" / "canonical"

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
    names = sorted({normalize_text(row["raw_exam_name"]) for row in rows if row.get("raw_exam_name")})
    return {name: f"LAB_{idx:06d}" for idx, name in enumerate(names, start=1)}


def load_siglario():
    allowed = read_csv(STAGING_DIR / "siglario_allowed_raw.csv")
    ambiguous = read_csv(STAGING_DIR / "siglario_ambiguous_raw.csv")
    institutional = read_csv(STAGING_DIR / "siglario_institucional_raw.csv")
    prohibited = read_csv(STAGING_DIR / "siglario_prohibited_raw.csv")
    return allowed, ambiguous, institutional, prohibited


def build_metadata_yaml(payload: dict) -> str:
    lines = []
    for key, value in payload.items():
        if isinstance(value, dict):
            lines.append(f"{key}:")
            for sub_key, sub_value in value.items():
                lines.append(f"  {sub_key}: {sub_value}")
        else:
            lines.append(f"{key}: {value}")
    return "\n".join(lines) + "\n"


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
        add_entry(entries, name, code, "official", "safe", row.get("source", "cid10_raw.csv"))
        add_entry(entries, code, code, "code", "safe", row.get("source", "cid10_raw.csv"))
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
        add_entry(entries, term, code, "official", "safe", row.get("source", "tuss_proc_raw.csv"))
        add_entry(entries, code, code, "code", "safe", row.get("source", "tuss_proc_raw.csv"))
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
        add_entry(entries, name, code, "official", "safe", row.get("source", "tuss_drugs_raw.csv"))
        add_entry(entries, code, code, "code", "safe", row.get("source", "tuss_drugs_raw.csv"))
        entry_type_counts["official"] += 1
        entry_type_counts["code"] += 1
        vocab_counts["TUSS_DRUG"] += 1

    # Labs
    lab_rows = read_csv(STAGING_DIR / "labs_raw.csv")
    lab_ids = build_labs_ids(lab_rows)
    for row in lab_rows:
        name = normalize_text(row.get("raw_exam_name"))
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
        add_entry(entries, name, concept_id, "official", "safe", row.get("source", "labs_raw.csv"))
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

    for abbr, meaning, source_file, version in sigla_rows:
        if not abbr or not meaning:
            continue
        meanings = sigla_map[abbr]
        is_ambiguous = len(meanings) > 1
        match_policy = "context_required" if is_ambiguous else "safe"
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
        add_entry(entries, abbr, concept_id, "abbr", match_policy, source_file)
        add_entry(entries, meaning, concept_id, "official", match_policy, source_file)
        entry_type_counts["abbr"] += 1
        entry_type_counts["official"] += 1
        vocab_counts["SIGLARIO"] += 1

        if is_ambiguous:
            possible_meanings = "; ".join(sorted(meanings))
            context_rule = context_map.get(f"{abbr}|{meaning}") or context_map.get(abbr, "")
            ambiguity_rows.append(
                {
                    "entry_text": abbr,
                    "concept_id": concept_id,
                    "conflict_type": "multiple_meanings",
                    "possible_meanings": possible_meanings,
                    "context_rule": context_rule,
                    "source_file": source_file,
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

    # Metadata
    counts = {
        "concepts": len(concepts_rows),
        "entries": len(entries_rows),
        "blocked_terms": len(blocked_terms),
        "ambiguity": len(ambiguity_rows),
    }
    hash_payload = f"{counts}|{len(entries)}|{len(concepts)}"
    metadata = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "staging_dir": str(STAGING_DIR),
        "canonical_dir": str(CANONICAL_DIR),
        "counts": counts,
        "vocabulary_breakdown": dict(vocab_counts),
        "entry_type_breakdown": dict(entry_type_counts),
        "hash": hashlib.sha256(hash_payload.encode("utf-8")).hexdigest(),
    }
    metadata_path = CANONICAL_DIR / "metadata.yaml"
    metadata_path.write_text(build_metadata_yaml(metadata), encoding="utf-8")

    # Summary
    LOG.info("Concepts: %s | Entries: %s", counts["concepts"], counts["entries"])
    LOG.info("Entry types: %s", dict(entry_type_counts))
    LOG.info("Vocab breakdown: %s", dict(vocab_counts))


if __name__ == "__main__":
    main()
