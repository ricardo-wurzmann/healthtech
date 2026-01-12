"""
Re-anchor gold entity offsets onto canonical raw_text.

Usage (from nlp_clin/):
    python -m eval.fix_gold_offsets \
      --in data/gold/template.with_offsets.jsonl \
      --out data/gold/template.with_offsets.fixed.jsonl \
      --report data/gold/fix_offsets_report.json \
      --text-field raw_text \
      --entities-field gold_entities \
      --entity-text-field text \
      --start-field start \
      --end-field end
"""
from __future__ import annotations

import argparse
import json
import re
import unicodedata
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple


@dataclass
class ReanchorResult:
    status: str
    old_start: Optional[int]
    old_end: Optional[int]
    new_start: Optional[int]
    new_end: Optional[int]
    method: Optional[str] = None
    message: Optional[str] = None


def normalize_for_search(text: str) -> str:
    """
    Lightweight normalization for searching:
    - Unicode NFKC
    - NBSP -> space
    - lowercase
    - collapse whitespace to single space
    - normalize common hyphens to '-'
    """
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\u00A0", " ")
    text = text.lower()
    # normalize common dash variants to '-'
    text = text.replace("–", "-").replace("—", "-")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _build_whitespace_tolerant_pattern(entity_text: str) -> str:
    """
    Build a regex pattern from entity_text that tolerates flexible whitespace.
    Operates directly on original raw_text; indices remain in original space.
    """
    # Escape everything, then replace escaped whitespace with \s+
    escaped = re.escape(entity_text)
    # Any sequence of escaped whitespace characters -> \s+
    pattern = re.sub(r"(\\\s)+", r"\\s+", escaped)
    return pattern


def _find_all_exact(raw_text: str, entity_text: str, start_hint: Optional[int] = None,
                    window: int = 250) -> List[Tuple[int, int, str]]:
    """
    Find all exact (case-sensitive and case-insensitive) matches of entity_text in raw_text.

    Returns list of (start, end, method) where method is 'exact_cs' or 'exact_ci'.
    """
    matches: List[Tuple[int, int, str]] = []
    if not entity_text:
        return matches

    # 1) Case-sensitive search (within window if start_hint given)
    def _search(sub_text: str, offset: int, method: str) -> None:
        idx = sub_text.find(entity_text)
        while idx != -1:
            start = offset + idx
            end = start + len(entity_text)
            matches.append((start, end, method))
            idx = sub_text.find(entity_text, idx + 1)

    if start_hint is not None:
        s = max(0, start_hint - window)
        e = min(len(raw_text), start_hint + window)
        _search(raw_text[s:e], s, "exact_cs_window")
    else:
        _search(raw_text, 0, "exact_cs_global")

    # 2) Case-insensitive search by normalizing both sides for comparison,
    # but still using original indices via regex.
    pattern_ci = re.compile(re.escape(entity_text), re.IGNORECASE)
    if start_hint is not None:
        s = max(0, start_hint - window)
        e = min(len(raw_text), start_hint + window)
        for m in pattern_ci.finditer(raw_text, s, e):
            matches.append((m.start(), m.end(), "exact_ci_window"))
    else:
        for m in pattern_ci.finditer(raw_text):
            matches.append((m.start(), m.end(), "exact_ci_global"))

    return matches


def _find_all_regex(raw_text: str, entity_text: str, start_hint: Optional[int] = None,
                    window: int = 250) -> List[Tuple[int, int, str]]:
    """
    Find all whitespace-tolerant regex matches of entity_text in raw_text.

    Returns list of (start, end, method).
    """
    pattern_str = _build_whitespace_tolerant_pattern(entity_text)
    try:
        pattern = re.compile(pattern_str, re.IGNORECASE)
    except re.error:
        return []

    matches: List[Tuple[int, int, str]] = []

    if start_hint is not None:
        s = max(0, start_hint - window)
        e = min(len(raw_text), start_hint + window)
        for m in pattern.finditer(raw_text, s, e):
            matches.append((m.start(), m.end(), "regex_window"))
    else:
        for m in pattern.finditer(raw_text):
            matches.append((m.start(), m.end(), "regex_global"))

    return matches


def _choose_best_match(matches: List[Tuple[int, int, str]], old_start: Optional[int]) -> Tuple[int, int, str, str]:
    """
    Choose the most plausible match from a list, preferring closest to old_start when available.

    Returns (start, end, method, status) where status may be 'ok' or 'ambiguous'.
    """
    if not matches:
        raise ValueError("No matches provided")

    if len(matches) == 1 or old_start is None:
        # Single match or no hint: take first; consider ambiguous if >1
        start, end, method = matches[0]
        status = "ok" if len(matches) == 1 else "ambiguous"
        return start, end, method, status

    # Choose the match whose start is closest to old_start
    best = min(matches, key=lambda m: abs(m[0] - old_start))
    start, end, method = best
    status = "ok" if len(matches) == 1 else "ambiguous"
    return start, end, method, status


def reanchor_entity(
    raw_text: str,
    entity_text: str,
    old_start: Optional[int] = None,
    old_end: Optional[int] = None,
    window: int = 250,
) -> ReanchorResult:
    """
    Re-anchor a single entity onto raw_text, returning new offsets and status.

    Strategy:
    1) If old offsets already match (under exact or case-insensitive), mark unchanged.
    2) Try exact substring matches (window first, then global).
    3) Try whitespace-tolerant regex matches (window, then global).
    4) If multiple matches, pick the one closest to old_start (if available).
    5) If nothing found, mark unresolved.
    """
    if not raw_text or not entity_text:
        return ReanchorResult(
            status="unresolved",
            old_start=old_start,
            old_end=old_end,
            new_start=None,
            new_end=None,
            method=None,
            message="empty_raw_or_text",
        )

    # 1) Check if existing offsets are already valid
    if isinstance(old_start, int) and isinstance(old_end, int):
        if 0 <= old_start < old_end <= len(raw_text):
            span = raw_text[old_start:old_end]
            if span == entity_text or normalize_for_search(span) == normalize_for_search(entity_text):
                return ReanchorResult(
                    status="unchanged",
                    old_start=old_start,
                    old_end=old_end,
                    new_start=old_start,
                    new_end=old_end,
                    method="existing_ok",
                )

    # Accumulate matches in priority order
    all_matches: List[Tuple[int, int, str]] = []

    # 2) Exact substring matches (window+global, cs+ci)
    all_matches.extend(_find_all_exact(raw_text, entity_text, start_hint=old_start, window=window))

    # 3) Whitespace-tolerant regex matches
    all_matches.extend(_find_all_regex(raw_text, entity_text, start_hint=old_start, window=window))

    if not all_matches:
        return ReanchorResult(
            status="unresolved",
            old_start=old_start,
            old_end=old_end,
            new_start=None,
            new_end=None,
            method=None,
            message="no_match_found",
        )

    # Choose best match
    start, end, method, status = _choose_best_match(all_matches, old_start)

    # Final validation
    span = raw_text[start:end]
    if normalize_for_search(span) != normalize_for_search(entity_text):
        return ReanchorResult(
            status="unresolved",
            old_start=old_start,
            old_end=old_end,
            new_start=None,
            new_end=None,
            method=method,
            message="span_text_mismatch_after_match",
        )

    return ReanchorResult(
        status=status,
        old_start=old_start,
        old_end=old_end,
        new_start=start,
        new_end=end,
        method=method,
    )


def process_file(
    in_path: Path,
    out_path: Path,
    text_field: str,
    entities_field: str,
    entity_text_field: str,
    start_field: str,
    end_field: str,
) -> Dict[str, Any]:
    """
    Process JSONL file, re-anchoring all entities.
    """
    total_cases = 0
    total_entities = 0
    fixed_count = 0
    unchanged_count = 0
    unresolved_count = 0
    ambiguous_count = 0

    status_counts: Dict[str, int] = {}
    examples: Dict[str, List[Dict[str, Any]]] = {}

    lines_out: List[str] = []

    with in_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            case = json.loads(line)
            total_cases += 1

            raw_text = case.get(text_field) or ""
            entities: List[Dict[str, Any]] = case.get(entities_field, [])
            total_entities += len(entities)

            for ent in entities:
                ent_text = ent.get(entity_text_field) or ent.get("span") or ""
                old_start = ent.get(start_field)
                old_end = ent.get(end_field)

                res = reanchor_entity(raw_text, ent_text, old_start=old_start, old_end=old_end)

                status_counts[res.status] = status_counts.get(res.status, 0) + 1

                if res.status == "unchanged":
                    unchanged_count += 1
                    # keep offsets as-is
                elif res.status in ("ok", "ambiguous"):
                    fixed_count += 1
                    if res.status == "ambiguous":
                        ambiguous_count += 1
                    ent[start_field] = res.new_start
                    ent[end_field] = res.new_end
                    ent.setdefault("offset_fix_meta", {})
                    ent["offset_fix_meta"].update(
                        {
                            "status": res.status,
                            "method": res.method,
                            "old_start": res.old_start,
                            "old_end": res.old_end,
                        }
                    )
                    # Optionally record a few examples
                    if res.status not in examples:
                        examples[res.status] = []
                    if len(examples[res.status]) < 10:
                        span = raw_text[res.new_start:res.new_end] if res.new_start is not None and res.new_end is not None else ""
                        examples[res.status].append(
                            {
                                "case_id": case.get("case_id"),
                                "text": ent_text,
                                "old_start": old_start,
                                "old_end": old_end,
                                "new_start": res.new_start,
                                "new_end": res.new_end,
                                "span": span,
                                "method": res.method,
                            }
                        )
                else:
                    unresolved_count += 1
                    # Leave offsets as-is, but mark meta
                    ent.setdefault("offset_fix_meta", {})
                    ent["offset_fix_meta"].update(
                        {
                            "status": res.status,
                            "method": res.method,
                            "old_start": res.old_start,
                            "old_end": res.old_end,
                            "message": res.message,
                        }
                    )
                    if res.status not in examples:
                        examples[res.status] = []
                    if len(examples[res.status]) < 10:
                        examples[res.status].append(
                            {
                                "case_id": case.get("case_id"),
                                "text": ent_text,
                                "old_start": old_start,
                                "old_end": old_end,
                                "message": res.message,
                            }
                        )

            case[entities_field] = entities
            lines_out.append(json.dumps(case, ensure_ascii=False))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines_out), encoding="utf-8")

    summary = {
        "total_cases": total_cases,
        "total_entities": total_entities,
        "fixed_count": fixed_count,
        "unchanged_count": unchanged_count,
        "unresolved_count": unresolved_count,
        "ambiguous_count": ambiguous_count,
        "status_counts": status_counts,
        "examples": examples,
    }
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Re-anchor gold entity offsets onto canonical raw_text")
    parser.add_argument("--in", dest="in_file", type=str, required=True, help="Input JSONL gold file")
    parser.add_argument("--out", dest="out_file", type=str, required=True, help="Output JSONL file")
    parser.add_argument("--report", type=str, required=True, help="JSON report file with repair summary")

    parser.add_argument("--text-field", type=str, default="raw_text", help="Field name for document text")
    parser.add_argument("--entities-field", type=str, default="gold_entities", help="Field name for entities list")
    parser.add_argument("--entity-text-field", type=str, default="text", help="Field name for entity text/span")
    parser.add_argument("--start-field", type=str, default="start", help="Field name for entity start offset")
    parser.add_argument("--end-field", type=str, default="end", help="Field name for entity end offset")

    args = parser.parse_args()

    in_path = Path(args.in_file)
    out_path = Path(args.out_file)
    report_path = Path(args.report)

    summary = process_file(
        in_path=in_path,
        out_path=out_path,
        text_field=args.text_field,
        entities_field=args.entities_field,
        entity_text_field=args.entity_text_field,
        start_field=args.start_field,
        end_field=args.end_field,
    )

    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print("Fix gold offsets completed.")
    print(f"  Total cases: {summary['total_cases']}")
    print(f"  Total entities: {summary['total_entities']}")
    print(f"  Fixed: {summary['fixed_count']}")
    print(f"  Unchanged: {summary['unchanged_count']}")
    print(f"  Unresolved: {summary['unresolved_count']}")
    print(f"  Ambiguous: {summary['ambiguous_count']}")


if __name__ == "__main__":
    main()



