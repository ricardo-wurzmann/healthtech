from __future__ import annotations
import json
import argparse
from pathlib import Path

from src.ingest_json import load_json_cases
from src.preprocess import normalize_text
from src.segment import split_sentences
from src.baseline_ner import extract_entities_baseline
from src.context import classify_assertion
from src.schema import DocOut, EntityOut, LinkCandidate
from src.postprocess.filters import filter_entities, FilterConfig



def process_document(doc, text: str) -> DocOut:
    """
    Process a single document through the pipeline.
    
    Args:
        doc: Document object with doc_id, text, and optionally case_id, group
        text: Normalized text
    
    Returns:
        DocOut object with entities and metadata
    """
    sents = split_sentences(text)
    sentences = [(s.text, s.start, s.end) for s in sents]
    
    spans = extract_entities_baseline(text, sentences)
    
    # Convert EntitySpan to dict format for filtering
    entities_dict = []
    for e in spans:
        sentence_text = text[e.sentence_start:e.sentence_end]
        ent_start_in_sent = e.start - e.sentence_start
        ent_end_in_sent = e.end - e.sentence_start
        assertion = classify_assertion(
            sentence_text,
            ent_start_in_sent,
            ent_end_in_sent,
            e.type
        )

        
        entities_dict.append({
            "span": e.span,
            "start": e.start,
            "end": e.end,
            "type": e.type,
            "score": float(e.score),
            "assertion": assertion,
            "evidence": e.evidence,
        })
    
    # Apply filtering
    filter_config = FilterConfig()
    entities_filtered = filter_entities(entities_dict, text, filter_config)
    
    # Log filtering stats
    filtered_count = len(spans) - len(entities_filtered)
    if filtered_count > 0:
        print(f"  Filtered out {filtered_count} junk entities (kept {len(entities_filtered)}/{len(spans)})")
    
    # Convert back to EntityOut format
    entities_out = []
    for e_dict in entities_filtered:
        # MVP linking: ainda vazio (entra no próximo sprint)
        links = []
        icd10 = []
        
        entities_out.append(EntityOut(
            span=e_dict["span"],
            start=e_dict["start"],
            end=e_dict["end"],
            type=e_dict["type"],
            score=e_dict["score"],
            assertion=e_dict["assertion"],
            evidence=e_dict["evidence"],
            links=links,
            icd10=icd10,
        ))
    
    # Handle both new (with case_id/group) and legacy (without) Document objects
    case_id = getattr(doc, 'case_id', 0)
    group = getattr(doc, 'group', 'pdf')
    
    result = DocOut(
        doc_id=doc.doc_id,
        source=doc.source_path,
        text=text,
        entities=entities_out,
        case_id=case_id,
        group=group,
    )
    
    return result


def run_on_json(json_path: str | Path, out_dir: str | Path) -> None:
    """
    Process all cases from a JSON file and output one JSON per case.
    
    Args:
        json_path: Path to input JSON file
        out_dir: Directory to write output JSON files (one per case)
    """
    json_path = Path(json_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    
    # Load all cases
    documents = load_json_cases(json_path)
    
    print(f"Processing {len(documents)} cases from {json_path}")
    
    for doc in documents:
        # Normalize text (preserves accents in output, but normalizes for processing)
        text = normalize_text(doc.text)
        
        # Process through pipeline
        result = process_document(doc, text)
        
        # Write output file
        out_file = out_dir / f"{doc.doc_id}.json"
        out_file.write_text(
            json.dumps(result, default=lambda o: o.__dict__, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        print(f"  ✓ {doc.doc_id} -> {out_file}")
    
    print(f"\nCompleted: {len(documents)} cases processed -> {out_dir}")


# def run_on_pdf(pdf_path: str | Path, out_path: str | Path) -> None:
#     """
#     Legacy function for PDF processing (kept for backward compatibility).
#     """
#     from src.ingest import load_pdf_as_document
    
#     doc = load_pdf_as_document(pdf_path)
#     text = normalize_text(doc.text)
    
#     result = process_document(doc, text)
    
#     out_path = Path(out_path)
#     out_path.parent.mkdir(parents=True, exist_ok=True)
#     out_path.write_text(
#         json.dumps(result, default=lambda o: o.__dict__, ensure_ascii=False, indent=2),
#         encoding="utf-8"
#     )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run clinical NLP pipeline on JSON cases or PDF")
    parser.add_argument(
        "--input",
        type=str,
        help="Input JSON file with cases (or PDF for legacy mode)",
        default="data/raw/pepv1.json"
    )
    parser.add_argument(
        "--out_dir",
        type=str,
        help="Output directory for JSON cases (default: data/processed/cases)",
        default="data/processed/cases"
    )
    parser.add_argument(
        "--out",
        type=str,
        help="Output file for single PDF (legacy mode)",
        default=None
    )
    
    args = parser.parse_args()
    
    input_path = Path(args.input)
    
    if input_path.suffix.lower() == '.json':
        # JSON mode: process multiple cases
        run_on_json(args.input, args.out_dir)
    else:
        # PDF mode (legacy)
        out_path = args.out or Path("data/processed/pipeline_output.json")
        # run_on_pdf(args.input, out_path)
        print(f"OK -> {out_path}")
