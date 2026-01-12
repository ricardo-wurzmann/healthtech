"""
Sync gold JSONL raw_text with canonical raw_text from per-case prediction files.

Usage (from nlp_clin/):
    python -m eval.sync_gold_raw_text \
      --gold data/gold/template.jsonl \
      --cases_dir data/processed/cases \
      --out data/gold/template.synced.jsonl
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, Any, List


def load_canonical_texts(cases_dir: Path) -> Dict[str, str]:
    """
    Load canonical raw_text (or text) from per-case JSON files.

    Returns:
        Dict mapping case_id (str) -> canonical raw_text
    """
    mapping: Dict[str, str] = {}
    for case_file in sorted(cases_dir.glob("*.json")):
        with case_file.open("r", encoding="utf-8") as f:
            data = json.load(f)

        case_id = data.get("case_id") or data.get("doc_id")
        if case_id is None:
            continue
        case_id_str = str(case_id)

        # Prefer raw_text if present, otherwise fallback to text
        text = data.get("raw_text") or data.get("text") or data.get("normalized_text") or ""
        mapping[case_id_str] = text
    return mapping


def sync_gold_raw_text(
    gold_path: Path,
    cases_dir: Path,
    out_path: Path,
) -> Dict[str, Any]:
    """
    Sync raw_text in gold JSONL with canonical raw_text from cases_dir.

    Returns:
        Summary dict with counts and mismatches.
    """
    canonical = load_canonical_texts(cases_dir)

    total_cases = 0
    synced_cases = 0
    missing_cases: List[str] = []
    mismatched_lengths = 0

    lines_out: List[str] = []

    with gold_path.open("r", encoding="utf-8") as f_in:
        for line in f_in:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            total_cases += 1

            case_id = str(obj.get("case_id"))
            if case_id in canonical:
                canonical_text = canonical[case_id]
                if obj.get("raw_text") != canonical_text:
                    obj["raw_text"] = canonical_text
                    synced_cases += 1
                # length sanity check
                if len(obj["raw_text"]) != len(canonical_text):
                    mismatched_lengths += 1
            else:
                missing_cases.append(case_id)

            lines_out.append(json.dumps(obj, ensure_ascii=False))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines_out), encoding="utf-8")

    summary = {
        "total_cases": total_cases,
        "synced_cases": synced_cases,
        "missing_in_cases_dir": missing_cases,
        "mismatched_length_count": mismatched_lengths,
    }
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync gold raw_text with canonical case raw_text")
    parser.add_argument("--gold", type=str, required=True, help="Input gold JSONL file")
    parser.add_argument("--cases_dir", type=str, required=True, help="Directory with per-case JSON files")
    parser.add_argument("--out", type=str, required=True, help="Output JSONL file with synced raw_text")

    args = parser.parse_args()

    gold_path = Path(args.gold)
    cases_dir = Path(args.cases_dir)
    out_path = Path(args.out)

    summary = sync_gold_raw_text(gold_path, cases_dir, out_path)

    print("Sync completed.")
    print(f"  Total gold cases: {summary['total_cases']}")
    print(f"  Cases synced: {summary['synced_cases']}")
    if summary["missing_in_cases_dir"]:
        print(f"  Missing in cases_dir: {len(summary['missing_in_cases_dir'])} (e.g., {summary['missing_in_cases_dir'][:5]})")
    print(f"  Mismatched length count: {summary['mismatched_length_count']}")


if __name__ == "__main__":
    main()



