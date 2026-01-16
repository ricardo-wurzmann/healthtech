"""
Wrapper script for auto-filling offsets in gold annotations.

Usage (from nlp_clin/):
    python fill_offsets.py --gold data/gold/template.jsonl \
        --out data/gold/template.with_offsets.jsonl \
        --report data/gold/offset_fill_report.json
"""
import sys
from pathlib import Path

# Add src to path so we can import the eval package
sys.path.insert(0, str(Path(__file__).parent / "src"))

from eval.fill_offsets import main  # type: ignore


if __name__ == "__main__":
    main()




