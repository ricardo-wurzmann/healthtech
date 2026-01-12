"""
Unit tests for entity matching logic.
"""
import unittest
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from eval.matching import (
    compute_span_metrics,
    relaxed_match,
    match_entities,
    MatchMode,
)
from eval.schema import GoldEntity, PredEntity


class TestMatching(unittest.TestCase):
    """Test cases for entity matching."""
    
    def test_containment_match(self):
        """Test that 'cefaleia' inside 'cefaleia intensa' matches under containment."""
        gold = GoldEntity(
            start=0,
            end=15,  # "cefaleia intensa"
            text="cefaleia intensa",
            type="SYMPTOM"
        )
        pred = PredEntity(
            start=0,
            end=8,  # "cefaleia"
            span="cefaleia",
            type="SYMPTOM"
        )
        
        # Should match with containment mode
        is_match, reason = relaxed_match(
            gold, pred, overlap_threshold=0.5, match_mode=MatchMode.IOU_OR_CONTAINMENT
        )
        self.assertTrue(is_match)
        self.assertEqual(reason, "containment")
        
        # Should also match with full mode
        is_match, reason = relaxed_match(
            gold, pred, overlap_threshold=0.5, match_mode=MatchMode.IOU_OR_MIN_COV_OR_CONTAINMENT
        )
        self.assertTrue(is_match)
        self.assertIn(reason, ["containment", "min_cov"])
    
    def test_min_cov_match(self):
        """Test that min_cov matching works when IoU is low."""
        gold = GoldEntity(
            start=0,
            end=15,  # "cefaleia intensa" (15 chars)
            text="cefaleia intensa",
            type="SYMPTOM"
        )
        pred = PredEntity(
            start=0,
            end=8,  # "cefaleia" (8 chars)
            span="cefaleia",
            type="SYMPTOM"
        )
        
        # IoU = 8 / (8 + 15 - 8) = 8/15 ≈ 0.53, but min_cov = 8/8 = 1.0
        is_match, reason = relaxed_match(
            gold, pred, overlap_threshold=0.5, match_mode=MatchMode.IOU_OR_MIN_COV
        )
        self.assertTrue(is_match)
        self.assertIn(reason, ["iou", "min_cov"])
    
    def test_no_match_low_overlap(self):
        """Test that spans with low overlap don't match."""
        gold = GoldEntity(
            start=0,
            end=20,
            text="cefaleia intensa grave",
            type="SYMPTOM"
        )
        pred = PredEntity(
            start=15,
            end=20,  # Only "grave" overlaps
            span="grave",
            type="SYMPTOM"
        )
        
        # Very low IoU and min_cov, no containment
        is_match, reason = relaxed_match(
            gold, pred, overlap_threshold=0.5, match_mode=MatchMode.IOU_OR_MIN_COV_OR_CONTAINMENT
        )
        self.assertFalse(is_match)
    
    def test_multiple_candidates_best_match(self):
        """Test that best match is selected when multiple candidates exist."""
        gold = GoldEntity(
            start=0,
            end=8,  # "cefaleia"
            text="cefaleia",
            type="SYMPTOM"
        )
        
        # Candidate 1: exact match
        pred1 = PredEntity(
            start=0,
            end=8,
            span="cefaleia",
            type="SYMPTOM"
        )
        
        # Candidate 2: partial overlap
        pred2 = PredEntity(
            start=0,
            end=5,  # "cefal"
            span="cefal",
            type="SYMPTOM"
        )
        
        # Should prefer pred1 (exact match)
        matched, unmatched_gold, unmatched_pred = match_entities(
            [gold],
            [pred1, pred2],
            relaxed=True,
            overlap_threshold=0.5,
            match_mode=MatchMode.IOU_OR_MIN_COV_OR_CONTAINMENT
        )
        
        self.assertEqual(len(matched), 1)
        self.assertEqual(matched[0].pred, pred1)
        self.assertEqual(len(unmatched_pred), 1)
        self.assertEqual(unmatched_pred[0], pred2)
    
    def test_type_mismatch_no_match(self):
        """Test that entities with different types don't match."""
        gold = GoldEntity(
            start=0,
            end=8,
            text="cefaleia",
            type="SYMPTOM"
        )
        pred = PredEntity(
            start=0,
            end=8,
            span="cefaleia",
            type="TEST"  # Different type
        )
        
        is_match, reason = relaxed_match(
            gold, pred, overlap_threshold=0.5, match_mode=MatchMode.IOU_OR_MIN_COV_OR_CONTAINMENT
        )
        self.assertFalse(is_match)
        self.assertIsNone(reason)


if __name__ == "__main__":
    unittest.main()

