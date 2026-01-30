from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure imports like "from src..." work when running from repo root
THIS_FILE = Path(__file__).resolve()
NLP_CLIN_DIR = THIS_FILE.parents[1]  # .../nlp_clin
if str(NLP_CLIN_DIR) not in sys.path:
    sys.path.insert(0, str(NLP_CLIN_DIR))


from src.ingest_json import load_json_cases
from src.preprocess import normalize_text


def _resolve_data_path() -> Path:
    base_dir = Path(__file__).resolve().parents[1]
    return base_dir / "data" / "raw" / "pepv1.json"


def _preview(text: str, limit: int = 400) -> str:
    return text[:limit].replace("\n", "\\n")


def _select_docs(docs, case_id: int | None, doc_id: str | None, n: int):
    if doc_id:
        for doc in docs:
            if doc.doc_id == doc_id:
                return [doc]
        print(f"doc_id not found: {doc_id}")
        return []
    if case_id is not None:
        for doc in docs:
            if doc.case_id == case_id:
                return [doc]
        print(f"case_id not found: {case_id}")
        return []
    return docs[:n]


def main() -> int:
    parser = argparse.ArgumentParser(description="Show preprocess output for a few cases.")
    parser.add_argument("--n", type=int, default=3, help="Number of cases to show.")
    parser.add_argument("--case_id", type=int, help="Select a single case_id.")
    parser.add_argument("--doc_id", type=str, help="Select a single doc_id.")
    args = parser.parse_args()

    data_path = _resolve_data_path()
    docs = load_json_cases(data_path)

    selected_docs = _select_docs(docs, args.case_id, args.doc_id, args.n)
    if not selected_docs:
        return 1

    for doc in selected_docs:
        raw_text = doc.text
        clean_text = normalize_text(raw_text)

        print("=" * 80)
        print(f"case_id: {doc.case_id} | group: {doc.group} | doc_id: {doc.doc_id}")
        print("-" * 80)
        print("RAW:")
        print(_preview(raw_text))
        print("-" * 80)
        print("PREPROCESSED:")
        print(_preview(clean_text))
        print("-" * 80)
        print("DIFF SUMMARY:")
        print(f"  length: raw={len(raw_text)} clean={len(clean_text)}")
        print(f"  newlines: raw={raw_text.count(chr(10))} clean={clean_text.count(chr(10))}")
        print(f"  double spaces: raw={raw_text.count('  ')} clean={clean_text.count('  ')}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
