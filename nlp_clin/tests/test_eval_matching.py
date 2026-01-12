"""
Unit tests for evaluation matching logic.
"""
import unittest

from eval.schema import GoldEntity, PredEntity, GoldCase, PredCase
from eval.matching import strict_match, relaxed_match, compute_overlap, compute_overlap_ratio
from eval.metrics import _get_context, collect_error_examples


class TestMatching(unittest.TestCase):
    
    def test_strict_match_exact(self):
        """Test strict matching with exact spans."""
        gold = GoldEntity(start=10, end=20, text="dor epigástrica", type="SYMPTOM")
        pred = PredEntity(start=10, end=20, span="dor epigástrica", type="SYMPTOM")
        self.assertTrue(strict_match(gold, pred))
    
    def test_strict_match_different_offset(self):
        """Test strict matching fails with different offsets."""
        gold = GoldEntity(start=10, end=20, text="dor epigástrica", type="SYMPTOM")
        pred = PredEntity(start=11, end=20, span="dor epigástrica", type="SYMPTOM")
        self.assertFalse(strict_match(gold, pred))
    
    def test_strict_match_different_type(self):
        """Test strict matching fails with different types."""
        gold = GoldEntity(start=10, end=20, text="dor epigástrica", type="SYMPTOM")
        pred = PredEntity(start=10, end=20, span="dor epigástrica", type="TEST")
        self.assertFalse(strict_match(gold, pred))
    
    def test_relaxed_match_overlap(self):
        """Test relaxed matching with sufficient overlap."""
        from eval.matching import MatchMode
        gold = GoldEntity(start=10, end=25, text="dor epigástrica intensa", type="SYMPTOM")
        pred = PredEntity(start=10, end=20, span="dor epigástrica", type="SYMPTOM")
        # Should match if overlap >= 0.5
        is_match, _ = relaxed_match(gold, pred, overlap_threshold=0.5, match_mode=MatchMode.IOU)
        self.assertTrue(is_match)
    
    def test_relaxed_match_insufficient_overlap(self):
        """Test relaxed matching fails with insufficient overlap."""
        from eval.matching import MatchMode
        gold = GoldEntity(start=10, end=30, text="dor epigástrica intensa", type="SYMPTOM")
        pred = PredEntity(start=50, end=55, span="febre", type="SYMPTOM")
        # No overlap
        is_match, _ = relaxed_match(gold, pred, overlap_threshold=0.5, match_mode=MatchMode.IOU)
        self.assertFalse(is_match)
    
    def test_relaxed_match_different_type(self):
        """Test relaxed matching fails with different types even with overlap."""
        from eval.matching import MatchMode
        gold = GoldEntity(start=10, end=20, text="dor epigástrica", type="SYMPTOM")
        pred = PredEntity(start=10, end=20, span="dor epigástrica", type="TEST")
        is_match, _ = relaxed_match(gold, pred, overlap_threshold=0.5, match_mode=MatchMode.IOU)
        self.assertFalse(is_match)
    
    def test_compute_overlap_exact(self):
        """Test overlap computation for exact match."""
        overlap = compute_overlap(10, 20, 10, 20)
        self.assertEqual(overlap, 1.0)
    
    def test_compute_overlap_partial(self):
        """Test overlap computation for partial overlap."""
        # Gold: [10, 25], Pred: [10, 20]
        # Overlap: 10, Union: 25, IoU = 10/25 = 0.4
        overlap = compute_overlap(10, 25, 10, 20)
        self.assertAlmostEqual(overlap, 0.4, places=2)
    
    def test_compute_overlap_no_overlap(self):
        """Test overlap computation for no overlap."""
        overlap = compute_overlap(10, 20, 30, 40)
        self.assertEqual(overlap, 0.0)
    
    def test_compute_overlap_ratio(self):
        """Test overlap ratio computation."""
        # Gold: [10, 25] (len=15), Pred: [10, 20] (len=10)
        # Overlap: 10, Min length: 10, Ratio = 10/10 = 1.0
        ratio = compute_overlap_ratio(10, 25, 10, 20)
        self.assertAlmostEqual(ratio, 1.0, places=2)

    def test_get_context_handles_none_offsets(self):
        """_get_context should not raise when start/end are None."""
        ctx = _get_context("abc", None, None)
        self.assertIsInstance(ctx, str)

    def test_collect_error_examples_handles_none_offsets(self):
        """collect_error_examples should not raise when entities have None offsets."""
        gold_case = GoldCase(
            case_id="1",
            group="prontuario",
            raw_text="paciente com dor",
            gold_entities=[
                GoldEntity(start=None, end=None, text="dor", type="SYMPTOM", assertion="PRESENT"),
            ],
            metadata={},
        )
        pred_case = PredCase.from_dict(
            {
                "case_id": "1",
                "text": "paciente com dor",
                "entities": [
                    {"start": None, "end": None, "span": "dor", "type": "SYMPTOM", "assertion": "PRESENT"}
                ],
            }
        )

        # Should not raise
        collect_error_examples(
            matched=[],
            unmatched_gold=gold_case.gold_entities,
            unmatched_pred=pred_case.entities,
            gold_cases=[gold_case],
            pred_cases=[pred_case],
            max_examples=5,
        )


if __name__ == "__main__":
    unittest.main()

