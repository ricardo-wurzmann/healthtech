"""
Wrapper script for re-anchoring gold entity offsets.

Usage (from nlp_clin/):
    python fix_gold_offsets.py \
      --in data/gold/template.with_offsets.jsonl \
      --out data/gold/template.with_offsets.fixed.jsonl \
      --report data/gold/fix_offsets_report.json
"""
import sys
from pathlib import Path

# Add src to path so we can import the eval package
sys.path.insert(0, str(Path(__file__).parent / "src"))

from eval.fix_gold_offsets import main  # type: ignore


if __name__ == "__main__":
    main()



