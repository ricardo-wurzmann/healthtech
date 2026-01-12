"""
One-off script to convert the existing gold template into proper JSONL format.

Usage (from nlp_clin/):
    python fix_template_jsonl.py
"""
import json
from pathlib import Path


def main() -> None:
    root = Path(__file__).parent
    raw_path = root / "data" / "raw" / "pepv1.json"
    tmpl_path = root / "data" / "gold" / "template.jsonl"

    # Load raw cases (authoritative list of case_ids and texts)
    raw_data = json.loads(raw_path.read_text(encoding="utf-8"))

    # Load existing annotations from current (non-JSONL) template.
    # The current file looks like:
    #   "gold_entities":[
    #       { ...case1... }
    #       { ...case2... }
    #       ...
    #   ]
    # but it's not valid JSON because there are no commas between case objects.
    # We parse it manually into separate case JSON blocks.
    raw_text = tmpl_path.read_text(encoding="utf-8")
    lines = raw_text.splitlines()

    case_blocks: list[str] = []
    current_block: list[str] = []
    in_case = False

    for idx, line in enumerate(lines):
        stripped = line.strip()

        # Skip the top-level wrapper and closing bracket
        if idx == 0 and stripped.startswith("\"gold_entities\""):
            continue
        if stripped == "]":
            continue

        # Detect start of a case object (line with just '{' at this level)
        if not in_case and stripped.startswith("{"):
            in_case = True
            current_block = [line]
            continue

        if in_case:
            current_block.append(line)
            # End of case object (line with just '}')
            if stripped == "}":
                case_blocks.append("\n".join(current_block))
                current_block = []
                in_case = False

    # Parse each case block as JSON
    annot_cases = []
    for block in case_blocks:
        try:
            annot_cases.append(json.loads(block))
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Failed to parse annotation block:\n{block}\nError: {e}") from e

    # Index annotations by case_id
    ann_by_case: dict[str, dict] = {}
    for case in annot_cases:
        cid = str(case.get("case_id"))
        if not cid:
            continue
        ann_by_case[cid] = case

    lines: list[str] = []
    for case in raw_data:
        cid = str(case.get("case_id"))
        group = case.get("group", "")
        raw_text = case.get("raw_text") or ""

        existing = ann_by_case.get(cid, {})
        gold_entities = existing.get("gold_entities", [])
        metadata = existing.get("metadata", {})
        if "annotator" not in metadata:
            metadata["annotator"] = ""
        if "version" not in metadata:
            metadata["version"] = "v1"

        obj = {
            "case_id": cid,
            "group": group,
            "raw_text": raw_text,
            "gold_entities": gold_entities,
            "metadata": metadata,
        }
        lines.append(json.dumps(obj, ensure_ascii=False))

    tmpl_path.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()


