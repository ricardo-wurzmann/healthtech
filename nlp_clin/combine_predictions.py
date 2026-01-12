"""
Combine per-case prediction JSON files into a single predictions file.

Usage:
    python combine_predictions.py data/processed/cases/ predictions.json
"""
import json
import argparse
from pathlib import Path
from typing import List, Dict, Any


def combine_case_files(cases_dir: Path) -> List[Dict[str, Any]]:
    """Load all case JSON files from a directory."""
    cases = []
    for case_file in sorted(cases_dir.glob("*.json")):
        with open(case_file, 'r', encoding='utf-8') as f:
            case_data = json.load(f)
            cases.append(case_data)
    return cases


def main():
    parser = argparse.ArgumentParser(description="Combine per-case predictions into single file")
    parser.add_argument(
        "cases_dir",
        type=str,
        help="Directory containing per-case JSON files"
    )
    parser.add_argument(
        "output",
        type=str,
        help="Output JSON file path"
    )
    
    args = parser.parse_args()
    
    cases_dir = Path(args.cases_dir)
    output_path = Path(args.output)
    
    print(f"Loading cases from {cases_dir}...")
    cases = combine_case_files(cases_dir)
    print(f"  Found {len(cases)} cases")
    
    # Write combined file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(cases, f, ensure_ascii=False, indent=2)
    
    print(f"Combined predictions saved to {output_path}")


if __name__ == "__main__":
    main()

