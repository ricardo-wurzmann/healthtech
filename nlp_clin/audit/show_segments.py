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
from src.segment import split_sentences


def _resolve_data_path() -> Path:
    base_dir = Path(__file__).resolve().parents[1]
    return base_dir / "data" / "raw" / "pepv1.json"


def _one_line(text: str) -> str:
    return " ".join(text.split())


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
    parser = argparse.ArgumentParser(description="Show sentence segments for a few cases.")
    parser.add_argument("--n", type=int, default=2, help="Number of cases to show.")
    parser.add_argument("--case_id", type=int, help="Select a single case_id.")
    parser.add_argument("--doc_id", type=str, help="Select a single doc_id.")
    args = parser.parse_args()

    data_path = _resolve_data_path()
    docs = load_json_cases(data_path)

    selected_docs = _select_docs(docs, args.case_id, args.doc_id, args.n)
    if not selected_docs:
        return 1

    for doc in selected_docs:
        clean_text = normalize_text(doc.text)
        sentences = split_sentences(clean_text)

        print("=" * 80)
        print(f"case_id: {doc.case_id} | group: {doc.group} | doc_id: {doc.doc_id}")
        for idx, sent in enumerate(sentences):
            print(f"{idx:02d} [{sent.start}:{sent.end}] {_one_line(sent.text)}")
        print(f"Total sentences: {len(sentences)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
