"""
Create gold annotation template from input cases or pipeline predictions.

Usage:
    # From nlp_clin/ directory:
    python create_gold_template.py input_cases.json output_gold_template.jsonl
    python create_gold_template.py --from-predictions predictions.json output_gold_template.jsonl
    
    # Or from src/ directory:
    python -m eval.create_gold_template input_cases.json output_gold_template.jsonl
"""
from __future__ import annotations
import json
import argparse
from pathlib import Path
from typing import List, Dict, Any

from src.ingest_json import load_json_cases

# Import schema - try relative first, then absolute
try:
    from .schema import GoldCase, GoldEntity
except ImportError:
    from src.eval.schema import GoldCase, GoldEntity


def create_template_from_cases(cases_path: Path, include_predictions: bool = False, 
                               predictions_path: Path | None = None) -> List[GoldCase]:
    """
    Create gold template from input cases.
    
    Args:
        cases_path: Path to input JSON with cases
        include_predictions: If True, prefill with predicted entities
        predictions_path: Path to predictions JSON (if include_predictions is True)
    
    Returns:
        List of GoldCase objects
    """
    # Load cases
    if cases_path.suffix.lower() == '.json':
        documents = load_json_cases(cases_path)
    else:
        raise ValueError(f"Unsupported file format: {cases_path.suffix}")
    
    # Load predictions if requested
    pred_dict = {}
    if include_predictions and predictions_path:
        with open(predictions_path, 'r', encoding='utf-8') as f:
            pred_data = json.load(f)
        
        # Handle both list and dict formats
        if isinstance(pred_data, list):
            for case in pred_data:
                case_id = case.get("case_id") or case.get("doc_id", "")
                pred_dict[str(case_id)] = case
        elif isinstance(pred_data, dict):
            # Could be {case_id: case_data} or single case
            if "case_id" in pred_data or "doc_id" in pred_data:
                case_id = pred_data.get("case_id") or pred_data.get("doc_id", "")
                pred_dict[str(case_id)] = pred_data
            else:
                # Assume it's a dict of cases
                pred_dict = pred_data
    
    # Create template cases
    template_cases = []
    for doc in documents:
        case_id = str(doc.case_id) if doc.case_id else doc.doc_id
        
        # Get predicted entities if available
        gold_entities = []
        if include_predictions and case_id in pred_dict:
            pred_case = pred_dict[case_id]
            for ent in pred_case.get("entities", []):
                gold_entities.append(GoldEntity(
                    start=ent.get("start", 0),
                    end=ent.get("end", 0),
                    text=ent.get("span") or ent.get("text", ""),
                    type=ent.get("type", ""),
                    assertion=ent.get("assertion"),
                    notes="predicted",  # Mark as predicted for review
                ))
        
        template_case = GoldCase(
            case_id=case_id,
            group=doc.group,
            raw_text=doc.text,
            gold_entities=gold_entities,
            metadata={
                "annotator": "",
                "version": "v1",
                "source": str(cases_path),
            }
        )
        template_cases.append(template_case)
    
    return template_cases


def create_template_from_predictions(predictions_path: Path) -> List[GoldCase]:
    """
    Create gold template from pipeline predictions.
    
    Args:
        predictions_path: Path to predictions JSON
    
    Returns:
        List of GoldCase objects
    """
    with open(predictions_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Handle both list and single case
    if isinstance(data, list):
        cases = data
    elif isinstance(data, dict):
        if "case_id" in data or "doc_id" in data:
            cases = [data]
        else:
            # Assume dict of cases
            cases = list(data.values())
    else:
        raise ValueError(f"Unexpected predictions format: {type(data)}")
    
    template_cases = []
    for case in cases:
        case_id = case.get("case_id") or case.get("doc_id", "")
        raw_text = case.get("text") or case.get("raw_text", "")
        
        # Prefill with predicted entities
        gold_entities = []
        for ent in case.get("entities", []):
            gold_entities.append(GoldEntity(
                start=ent.get("start", 0),
                end=ent.get("end", 0),
                text=ent.get("span") or ent.get("text", ""),
                type=ent.get("type", ""),
                assertion=ent.get("assertion"),
                notes="predicted",  # Mark for review
            ))
        
        template_case = GoldCase(
            case_id=case_id,
            group=case.get("group"),
            raw_text=raw_text,
            gold_entities=gold_entities,
            metadata={
                "annotator": "",
                "version": "v1",
                "source": str(predictions_path),
            }
        )
        template_cases.append(template_case)
    
    return template_cases


def write_jsonl(cases: List[GoldCase], output_path: Path):
    """Write cases to JSONL file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        for case in cases:
            f.write(json.dumps(case.to_dict(), ensure_ascii=False) + '\n')


def main():
    parser = argparse.ArgumentParser(
        description="Create gold annotation template from cases or predictions"
    )
    parser.add_argument(
        "input",
        type=str,
        help="Input JSON file (cases or predictions)"
    )
    parser.add_argument(
        "output",
        type=str,
        help="Output JSONL file for gold annotations"
    )
    parser.add_argument(
        "--from-predictions",
        action="store_true",
        help="Input is pipeline predictions (not raw cases)"
    )
    parser.add_argument(
        "--prefill",
        type=str,
        help="Path to predictions JSON to prefill template with predicted entities"
    )
    
    args = parser.parse_args()
    
    input_path = Path(args.input)
    output_path = Path(args.output)
    
    if args.from_predictions:
        template_cases = create_template_from_predictions(input_path)
    else:
        pred_path = Path(args.prefill) if args.prefill else None
        template_cases = create_template_from_cases(
            input_path,
            include_predictions=(pred_path is not None),
            predictions_path=pred_path
        )
    
    write_jsonl(template_cases, output_path)
    print(f"Created template with {len(template_cases)} cases -> {output_path}")


if __name__ == "__main__":
    main()

