"""
Auto-fill missing character offsets for gold entities based on raw_text.

Usage (from nlp_clin/):
    python -m eval.fill_offsets --gold data/gold/template.jsonl \
        --out data/gold/template.with_offsets.jsonl \
        --report data/gold/offset_fill_report.json
"""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any, Tuple

from unidecode import unidecode


@dataclass
class OffsetFillStats:
    total_cases: int = 0
    total_entities: int = 0
    filled_count: int = 0
    ambiguous_count: int = 0
    not_found_count: int = 0


def normalize_for_match(text: str) -> str:
    """
    Normalize text for matching:
    - lowercased
    - accent-insensitive (unidecode)
    - collapse whitespace
    """
    text = unidecode(text.lower())
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def find_matches(raw_text: str, entity_text: str) -> List[Tuple[int, int]]:
    """
    Find all matches of entity_text in raw_text, returning (start, end) indices.

    Matching is:
    - case-insensitive
    - accent-insensitive
    - tolerant to multiple spaces
    """
    if not entity_text:
        return []

    norm_raw = normalize_for_match(raw_text)
    norm_ent = normalize_for_match(entity_text)
    if not norm_ent:
        return []

    # Build a regex that allows flexible whitespace in the normalized space.
    # We escape non-space characters but replace spaces with \s+.
    pattern_escaped = re.escape(norm_ent)
    pattern_escaped = re.sub(r"\\\s+", r"\\s+", pattern_escaped)
    norm_regex = re.compile(pattern_escaped)

    matches: List[Tuple[int, int]] = []

    for norm_match in norm_regex.finditer(norm_raw):
        norm_start, norm_end = norm_match.start(), norm_match.end()

        # Map back to original text by sliding a window and comparing normalized text.
        # This is approximate but safe for evaluation purposes.
        # We search in a window around the proportional position.
        approx_start = max(0, int(norm_start * len(raw_text) / max(len(norm_raw), 1)) - 20)
        approx_end = min(len(raw_text), approx_start + len(entity_text) + 200)
        window = raw_text[approx_start:approx_end]
        norm_window = normalize_for_match(window)

        # Find the normalized entity text inside the normalized window
        inner_idx = norm_window.find(norm_ent)
        if inner_idx == -1:
            continue

        # Map inner_idx back to original indices by scanning characters
        # and tracking normalized length.
        norm_count = 0
        start_in_window = None
        end_in_window = None

        for i, ch in enumerate(window):
            chunk = normalize_for_match(ch)
            if not chunk:
                continue
            if start_in_window is None and norm_count >= inner_idx:
                start_in_window = i
            norm_count += len(chunk)
            if start_in_window is not None and norm_count >= inner_idx + len(norm_ent):
                end_in_window = i + 1
                break

        if start_in_window is None or end_in_window is None:
            continue

        start = approx_start + start_in_window
        end = approx_start + end_in_window
        matches.append((start, end))

    return matches


def fill_offsets_for_case(
    case: Dict[str, Any],
    stats: OffsetFillStats,
    examples: Dict[str, List[Dict[str, Any]]],
    allow_ambiguous_best_effort: bool = False,
) -> Dict[str, Any]:
    """Fill missing offsets for a single case."""
    raw_text: str = case.get("raw_text") or ""
    entities: List[Dict[str, Any]] = case.get("gold_entities", [])

    stats.total_cases += 1
    stats.total_entities += len(entities)

    for ent in entities:
        start = ent.get("start")
        end = ent.get("end")

        # Leave existing offsets unchanged
        if isinstance(start, int) and isinstance(end, int):
            continue

        text = ent.get("text") or ""
        if not text or not raw_text:
            stats.not_found_count += 1
            examples.setdefault("not_found", []).append(
                {"case_id": case.get("case_id"), "text": text, "reason": "empty_text_or_raw"}
            )
            continue

        spans = find_matches(raw_text, text)
        if len(spans) == 1:
            s, e = spans[0]
            ent["start"] = s
            ent["end"] = e
            stats.filled_count += 1
        elif len(spans) == 0:
            stats.not_found_count += 1
            examples.setdefault("not_found", []).append(
                {
                    "case_id": case.get("case_id"),
                    "text": text,
                    "match_count": 0,
                }
            )
        else:
            # Ambiguous
            stats.ambiguous_count += 1
            examples.setdefault("ambiguous", []).append(
                {
                    "case_id": case.get("case_id"),
                    "text": text,
                    "match_count": len(spans),
                }
            )
            if allow_ambiguous_best_effort:
                s, e = spans[0]
                ent["start"] = s
                ent["end"] = e

    # Return updated case
    case["gold_entities"] = entities
    return case


def main() -> None:
    parser = argparse.ArgumentParser(description="Auto-fill missing offsets in gold JSONL file")
    parser.add_argument(
        "--gold",
        type=str,
        required=True,
        help="Input gold JSONL file",
    )
    parser.add_argument(
        "--out",
        type=str,
        required=True,
        help="Output JSONL file with filled offsets",
    )
    parser.add_argument(
        "--report",
        type=str,
        required=True,
        help="Output JSON report with filling statistics",
    )
    parser.add_argument(
        "--cases_dir",
        type=str,
        required=False,
        help="Optional: directory with canonical per-case JSON files to sync raw_text before filling",
    )
    parser.add_argument(
        "--allow-ambiguous-best-effort",
        action="store_true",
        help="If set, for ambiguous matches pick the first match as best effort (default: do not fill ambiguous)",
    )

    args = parser.parse_args()

    gold_path = Path(args.gold)
    out_path = Path(args.out)
    report_path = Path(args.report)

    stats = OffsetFillStats()
    examples: Dict[str, List[Dict[str, Any]]] = {}

    updated_cases: List[Dict[str, Any]] = []

    # Optional: sync raw_text with canonical texts from cases_dir
    canonical: Dict[str, str] = {}
    if args.cases_dir:
        from .sync_gold_raw_text import load_canonical_texts  # type: ignore

        canonical = load_canonical_texts(Path(args.cases_dir))

    with gold_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            case = json.loads(line)
            # Replace raw_text if we have a canonical version
            if canonical:
                cid = str(case.get("case_id"))
                if cid in canonical:
                    case["raw_text"] = canonical[cid]

            updated = fill_offsets_for_case(
                case, stats, examples, allow_ambiguous_best_effort=args.allow_ambiguous_best_effort
            )
            updated_cases.append(updated)

    # Write updated JSONL
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f_out:
        for case in updated_cases:
            f_out.write(json.dumps(case, ensure_ascii=False) + "\n")

    # Build report
    report: Dict[str, Any] = {
        "total_cases": stats.total_cases,
        "total_entities": stats.total_entities,
        "filled_count": stats.filled_count,
        "ambiguous_count": stats.ambiguous_count,
        "not_found_count": stats.not_found_count,
        "examples": {
            "ambiguous": examples.get("ambiguous", [])[:20],
            "not_found": examples.get("not_found", [])[:20],
        },
    }

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()


