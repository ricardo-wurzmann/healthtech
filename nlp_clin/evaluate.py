"""
Wrapper script for evaluation.

Usage:
    python evaluate.py --pred predictions.json --gold gold.jsonl --out report.json
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Import and run main
from eval.evaluate import main

if __name__ == "__main__":
    main()

