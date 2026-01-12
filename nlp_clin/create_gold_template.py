"""
Wrapper script for creating gold annotation templates.

Usage:
    python create_gold_template.py input_cases.json output_gold_template.jsonl
    python create_gold_template.py --from-predictions predictions.json output_gold_template.jsonl
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Import and run main
from eval.create_gold_template import main

if __name__ == "__main__":
    main()

