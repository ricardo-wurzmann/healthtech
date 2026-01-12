"""
Wrapper script for printing evaluation reports.

Usage:
    python report.py --report report.json
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

# Import and run main
from eval.report import main

if __name__ == "__main__":
    main()

