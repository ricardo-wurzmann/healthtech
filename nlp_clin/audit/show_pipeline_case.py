from __future__ import annotations

import argparse
import difflib
import re
import sys
from pathlib import Path


THIS_FILE = Path(__file__).resolve()
NLP_CLIN_DIR = THIS_FILE.parents[1]
if str(NLP_CLIN_DIR) not in sys.path:
    sys.path.insert(0, str(NLP_CLIN_DIR))


def _import_or_exit(module_label: str, import_stmt: str):
    try:
        exec(import_stmt, globals())
    except Exception as exc:  # noqa: BLE001 - keep broad for audit script
        print(f"Could not import {module_label}: {exc}")
        raise SystemExit(1)


_import_or_exit("loader from src.ingest_json", "from src.ingest_json import load_json_cases")
_import_or_exit("preprocess from src.preprocess", "from src.preprocess import normalize_text")
_import_or_exit("segmenter from src.segment", "from src.segment import split_sentences")
_import_or_exit("baseline NER from src.baseline_ner", "from src.baseline_ner import extract_entities_baseline")
_import_or_exit("assertion from src.context", "from src.context import classify_assertion")


def _resolve_data_path() -> Path:
    return NLP_CLIN_DIR / "data" / "raw" / "pepv1.json"


def _text_stats(text: str) -> dict:
    return {
        "len": len(text),
        "newlines": text.count("\n"),
        "double_spaces": text.count("  "),
    }


def _preview(text: str, limit: int) -> str:
    return text[:limit].replace("\n", "\\n")


def _diff_spans(raw: str, clean: str, max_spans: int = 3):
    matcher = difflib.SequenceMatcher(None, raw, clean)
    spans = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        spans.append((tag, i1, i2, j1, j2))
        if len(spans) >= max_spans:
            break
    return spans


def _snippet(text: str, start: int, end: int, max_len: int = 80) -> str:
    snippet = text[start:end].replace("\n", "\\n")
    if len(snippet) > max_len:
        snippet = snippet[:max_len] + "..."
    return snippet


def _select_doc(docs, case_id: int | None, doc_id: str | None):
    if doc_id:
        for doc in docs:
            if doc.doc_id == doc_id:
                return doc
        print(f"doc_id not found: {doc_id}")
        raise SystemExit(1)
    if case_id is not None:
        for doc in docs:
            if doc.case_id == case_id:
                return doc
        print(f"case_id not found: {case_id}")
        raise SystemExit(1)
    return docs[0] if docs else None


def _infer_source(span: str, ent) -> str:
    allowed = {"pattern", "lexicon", "index", "fuzzy", "unknown"}
    for attr in ("source", "reason"):
        value = getattr(ent, attr, None)
        if isinstance(value, str) and value:
            normalized = value.lower().strip()
            return normalized if normalized in allowed else "unknown"
    s = span.lower()
    if re.search(r"\d", s) and (
        "x" in s or "/" in s or "bpm" in s or "mmhg" in s or "spo2" in s or "sat" in s
    ):
        return "pattern"
    if any(tok in s for tok in ("glasgow", "gcs", "ecg", "fast")):
        return "pattern"
    return "unknown"


def _one_line(text: str) -> str:
    return " ".join(text.split())


def main() -> int:
    parser = argparse.ArgumentParser(description="Show a single case through pipeline stages.")
    parser.add_argument("--case_id", type=int, help="Select case by case_id.")
    parser.add_argument("--doc_id", type=str, help="Select case by doc_id (wins over case_id).")
    parser.add_argument("--preview_chars", type=int, default=400, help="Preview length for raw/preprocessed.")
    parser.add_argument("--n_sent", type=int, default=50, help="Max number of sentences to show.")
    args = parser.parse_args()

    data_path = _resolve_data_path()
    docs = load_json_cases(data_path)
    doc = _select_doc(docs, args.case_id, args.doc_id)
    if doc is None:
        print("No documents found in dataset.")
        return 1

    raw_text = doc.text
    clean_text = normalize_text(raw_text)
    sentences = split_sentences(clean_text)
    sentence_tuples = [(s.text, s.start, s.end) for s in sentences]
    entities = extract_entities_baseline(clean_text, sentence_tuples)

    print("=" * 80)
    print(f"case_id: {doc.case_id} | group: {doc.group} | doc_id: {doc.doc_id}")
    print("=" * 80)

    # 1) RAW
    raw_stats = _text_stats(raw_text)
    print("RAW")
    print(_preview(raw_text, args.preview_chars))
    print(f"stats: len={raw_stats['len']} newlines={raw_stats['newlines']} double_spaces={raw_stats['double_spaces']}")
    print("=" * 80)

    # 2) PREPROCESSED
    clean_stats = _text_stats(clean_text)
    print("PREPROCESSED")
    print(_preview(clean_text, args.preview_chars))
    print(f"stats: len={clean_stats['len']} newlines={clean_stats['newlines']} double_spaces={clean_stats['double_spaces']}")
    print(
        "diff: "
        f"raw_len={raw_stats['len']} clean_len={clean_stats['len']} "
        f"raw_newlines={raw_stats['newlines']} clean_newlines={clean_stats['newlines']} "
        f"raw_double_spaces={raw_stats['double_spaces']} clean_double_spaces={clean_stats['double_spaces']}"
    )
    spans = _diff_spans(raw_text, clean_text, max_spans=3)
    if spans:
        for idx, (tag, i1, i2, j1, j2) in enumerate(spans, start=1):
            raw_snip = _snippet(raw_text, i1, i2)
            clean_snip = _snippet(clean_text, j1, j2)
            print(f"change {idx}: {tag} raw[{i1}:{i2}]='{raw_snip}' -> clean[{j1}:{j2}]='{clean_snip}'")
    else:
        print("change 1: no differences found")
    print("=" * 80)

    # 3) SEGMENTS
    print("SEGMENTS")
    for idx, sent in enumerate(sentences[: args.n_sent]):
        print(f"{idx:02d} [{sent.start}:{sent.end}] {_one_line(sent.text)}")
    print(f"Total sentences: {len(sentences)}")
    print("=" * 80)

    # 4) BASELINE_NER
    print("BASELINE_NER")
    for idx, sent in enumerate(sentences[: args.n_sent]):
        print(f"SENT {idx:02d} [{sent.start}:{sent.end}] {_one_line(sent.text)}")
        sent_entities = [
            e for e in entities if e.start >= sent.start and e.end <= sent.end
        ]
        if not sent_entities:
            continue
        for e in sent_entities:
            rel_start = e.start - sent.start
            rel_end = e.end - sent.start
            assertion_ctx = classify_assertion(sent.text, rel_start, rel_end, e.type)
            model_assertion = getattr(e, "assertion", None)
            source = _infer_source(e.span, e)
            if model_assertion and model_assertion != assertion_ctx:
                assertion_str = f"assertion_model={model_assertion} assertion_ctx={assertion_ctx}"
            else:
                assertion_str = f"assertion={assertion_ctx}"
            print(
                f'- {e.type} "{e.span}" [{e.start}:{e.end}] '
                f"sent_rel=[{rel_start}:{rel_end}] {assertion_str} score={e.score:.3f} source={source}"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
