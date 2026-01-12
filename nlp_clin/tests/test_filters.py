"""
Unit tests for entity filtering.
"""
import unittest
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from postprocess.filters import (
    filter_entities,
    FilterConfig,
    tokenize_span,
    trim_punctuation,
    normalize_token,
)


class TestFilters(unittest.TestCase):
    """Test cases for entity filtering."""
    
    def test_filter_stopword_only_span(self):
        """Test that 'com' type=SYMPTOM is dropped."""
        entities = [
            {
                "span": "com",
                "start": 0,
                "end": 3,
                "type": "SYMPTOM"
            }
        ]
        raw_text = "com"
        
        filtered = filter_entities(entities, raw_text)
        self.assertEqual(len(filtered), 0)
    
    def test_filter_relatando(self):
        """Test that 'relatando' type=SYMPTOM is dropped."""
        entities = [
            {
                "span": "relatando",
                "start": 0,
                "end": 9,
                "type": "SYMPTOM"
            }
        ]
        raw_text = "relatando"
        
        filtered = filter_entities(entities, raw_text)
        self.assertEqual(len(filtered), 0)
    
    def test_keep_valid_symptom(self):
        """Test that 'dor abdominal' type=SYMPTOM is kept."""
        entities = [
            {
                "span": "dor abdominal",
                "start": 0,
                "end": 13,
                "type": "SYMPTOM"
            }
        ]
        raw_text = "dor abdominal"
        
        filtered = filter_entities(entities, raw_text)
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["span"], "dor abdominal")
    
    def test_trim_punctuation(self):
        """Test that 'dor,' becomes 'dor' with updated offsets."""
        entities = [
            {
                "span": "dor,",
                "start": 0,
                "end": 4,
                "type": "SYMPTOM"
            }
        ]
        raw_text = "dor,"
        
        config = FilterConfig(trim_punct=True)
        filtered = filter_entities(entities, raw_text, config)
        
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["span"], "dor")
        self.assertEqual(filtered[0]["start"], 0)
        self.assertEqual(filtered[0]["end"], 3)
    
    def test_non_symptom_not_filtered(self):
        """Test that non-SYMPTOM types are not filtered unless configured."""
        entities = [
            {
                "span": "com",
                "start": 0,
                "end": 3,
                "type": "TEST"  # Not SYMPTOM
            }
        ]
        raw_text = "com"
        
        # Default config only filters SYMPTOM
        filtered = filter_entities(entities, raw_text)
        self.assertEqual(len(filtered), 1)  # Kept because not SYMPTOM
        
        # But if we configure to filter TEST too
        config = FilterConfig(apply_to_types={"TEST"})
        filtered = filter_entities(entities, raw_text, config)
        self.assertEqual(len(filtered), 0)  # Filtered
    
    def test_min_length_filter(self):
        """Test that spans shorter than min_chars are filtered."""
        entities = [
            {
                "span": "abc",  # 3 chars < 4
                "start": 0,
                "end": 3,
                "type": "SYMPTOM"
            }
        ]
        raw_text = "abc"
        
        filtered = filter_entities(entities, raw_text)
        self.assertEqual(len(filtered), 0)
    
    def test_invalid_offsets_filtered(self):
        """Test that entities with invalid offsets are filtered."""
        entities = [
            {
                "span": "dor",
                "start": -1,  # Invalid
                "end": 3,
                "type": "SYMPTOM"
            },
            {
                "span": "dor",
                "start": 0,
                "end": 100,  # Out of bounds
                "type": "SYMPTOM"
            },
            {
                "span": "dor",
                "start": 5,
                "end": 3,  # end <= start
                "type": "SYMPTOM"
            }
        ]
        raw_text = "dor"
        
        filtered = filter_entities(entities, raw_text)
        self.assertEqual(len(filtered), 0)
    
    def test_symptom_nucleus_required(self):
        """Test that SYMPTOM spans must contain a nucleus token."""
        entities = [
            {
                "span": "à palpação do",  # No nucleus
                "start": 0,
                "end": 13,
                "type": "SYMPTOM"
            },
            {
                "span": "dor abdominal",  # Has "dor" nucleus
                "start": 0,
                "end": 13,
                "type": "SYMPTOM"
            }
        ]
        raw_text = "à palpação do dor abdominal"
        
        filtered = filter_entities(entities, raw_text)
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["span"], "dor abdominal")
    
    def test_tokenize_span(self):
        """Test tokenization."""
        tokens = tokenize_span("dor abdominal")
        self.assertEqual(tokens, ["dor", "abdominal"])
        
        tokens = tokenize_span("dor, abdominal.")
        self.assertEqual(tokens, ["dor", "abdominal"])
    
    def test_normalize_token(self):
        """Test token normalization."""
        self.assertEqual(normalize_token("Dor"), "dor")
        self.assertEqual(normalize_token("Cefaléia"), "cefaleia")
        self.assertEqual(normalize_token("  NÁUSEA  "), "nausea")


if __name__ == "__main__":
    unittest.main()

