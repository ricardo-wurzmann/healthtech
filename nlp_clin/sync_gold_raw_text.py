"""
Wrapper script for syncing gold raw_text with canonical case raw_text.

Usage (from nlp_clin/):
    python sync_gold_raw_text.py \
      --gold data/gold/template.jsonl \
      --cases_dir data/processed/cases \
      --out data/gold/template.synced.jsonl
"""
import sys
from pathlib import Path

# Add src to path so we can import the eval package
sys.path.insert(0, str(Path(__file__).parent / "src"))

from eval.sync_gold_raw_text import main  # type: ignore


if __name__ == "__main__":
    main()



