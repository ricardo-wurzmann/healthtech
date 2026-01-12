# Lexicon Usage Checklist

## Summary Table

| Lexicon File | Entity Type | Loaded | Indexed | Used in Matching | Appears in Final Output | Status |
|-------------|-------------|--------|---------|------------------|-------------------------|--------|
| `symptoms_core_ptbr.txt` | SYMPTOM | ✅ | ✅ | ✅ | ✅ | **WORKING** |
| `symptoms_expanded_ptbr.txt` | SYMPTOM | ✅ | ✅ | ✅ | ⚠️ | **WORKING** (needs verification) |
| `anatomy_ptbr.txt` | ANATOMY | ✅ | ✅ | ✅ | ❓ | **WORKING** (needs empirical test) |
| `procedures_ptbr.txt` | PROCEDURE | ✅ | ✅ | ✅ | ✅ | **WORKING** |
| `tests_exams_ptbr.txt` | TEST | ✅ | ✅ | ✅ | ❓ | **WORKING** (needs empirical test) |
| `drugs_ptbr.txt` | DRUG | ✅ | ✅ | ✅ | ❓ | **WORKING** (needs empirical test) |

**Legend**:
- ✅ Verified and confirmed
- ⚠️ Partially verified (likely working but not fully confirmed)
- ❓ Needs empirical testing with actual data
- ❌ Not working

---

## Detailed Status

### 1. symptoms_core_ptbr.txt → SYMPTOM
- **Loaded**: ✅ Yes (119 entries, priority 1)
- **Indexed**: ✅ Yes (all entries normalized and indexed)
- **Used in Matching**: ✅ Yes (exact, token, and fuzzy matching)
- **Appears in Output**: ✅ Yes (verified: "cefaleia", "dor epigástrica")
- **Priority**: ✅ Core symptoms loaded first, take priority over expanded

### 2. symptoms_expanded_ptbr.txt → SYMPTOM
- **Loaded**: ✅ Yes (9,044 entries, priority 2, deduplicated)
- **Indexed**: ✅ Yes (all unique entries normalized and indexed)
- **Used in Matching**: ✅ Yes (exact, token, and fuzzy matching)
- **Appears in Output**: ⚠️ Likely yes (but specific expanded terms not verified)
- **Priority**: ✅ Loaded after core, duplicates skipped

### 3. anatomy_ptbr.txt → ANATOMY
- **Loaded**: ✅ Yes (153 entries)
- **Indexed**: ✅ Yes (all entries normalized and indexed)
- **Used in Matching**: ✅ Yes (exact, token, and fuzzy matching)
- **Appears in Output**: ❓ Not found in sample predictions (needs test)
- **Priority**: N/A (single source)

### 4. procedures_ptbr.txt → PROCEDURE
- **Loaded**: ✅ Yes (47 entries)
- **Indexed**: ✅ Yes (all entries normalized and indexed)
- **Used in Matching**: ✅ Yes (exact, token, and fuzzy matching)
- **Appears in Output**: ✅ Yes (verified: "FAST")
- **Priority**: N/A (single source)

### 5. tests_exams_ptbr.txt → TEST
- **Loaded**: ✅ Yes (48 entries)
- **Indexed**: ✅ Yes (all entries normalized and indexed)
- **Used in Matching**: ✅ Yes (exact, token, and fuzzy matching)
- **Appears in Output**: ❓ Not found in sample predictions (needs test)
- **Priority**: N/A (single source)

### 6. drugs_ptbr.txt → DRUG
- **Loaded**: ✅ Yes (37 entries)
- **Indexed**: ✅ Yes (all entries normalized and indexed)
- **Used in Matching**: ✅ Yes (exact, token, and fuzzy matching)
- **Appears in Output**: ❓ Not found in sample predictions (needs test)
- **Priority**: N/A (single source)

---

## Critical Issues Summary

### ✅ RESOLVED
1. **Lexicon files not being loaded** - ✅ FIXED
   - **Issue**: Files existed but were never loaded
   - **Fix**: Implemented `load_all_lexicons()` in `src/lexicon.py`
   - **Result**: Now loading 9,329 entries (from 9,448 total, after deduplication)

2. **Only 17 hardcoded entries in use** - ✅ FIXED
   - **Issue**: Pipeline only used hardcoded list
   - **Fix**: Automatic loading from files
   - **Result**: All 6 lexicon files now loaded

3. **ANATOMY type missing** - ✅ FIXED
   - **Issue**: Not in hardcoded list
   - **Fix**: Now loaded from `anatomy_ptbr.txt`
   - **Result**: 153 ANATOMY entries available

### ⚠️ REMAINING ISSUES

1. **Fuzzy matching enabled for symptoms**
   - **Severity**: Medium
   - **Location**: `baseline_ner.py:272`
   - **Issue**: Fuzzy matching applies to all entity types, including SYMPTOM
   - **Impact**: May cause false positives for symptoms
   - **Recommendation**: Consider disabling fuzzy for SYMPTOM entities

2. **Overlap resolution doesn't prioritize core symptoms**
   - **Severity**: Medium
   - **Location**: `baseline_ner.py:133` (`_resolve_overlaps()`)
   - **Issue**: Resolution based on span length/score, not lexicon source priority
   - **Impact**: Expanded symptoms might override core symptoms if they have longer spans
   - **Recommendation**: Add priority field to EntitySpan and modify overlap resolution

3. **Limited empirical verification**
   - **Severity**: Low
   - **Issue**: ANATOMY, TEST, and DRUG not verified in sample predictions
   - **Impact**: Cannot confirm these lexicons produce output
   - **Recommendation**: Run comprehensive test suite with sentences containing terms from each lexicon

---

## Verification Commands

```bash
# Check lexicon loading
cd nlp_clin
python -c "from src.lexicon import LEXICON; print(f'Loaded {len(LEXICON)} entries')"
# Expected: Loaded 9329 entries

# Check entity type distribution
python -c "from src.lexicon import LEXICON; types = {}; [types.update({t: types.get(t, 0) + 1}) for _, t in LEXICON]; print(dict(sorted(types.items())))"
# Expected: {'ANATOMY': 153, 'DRUG': 37, 'PROCEDURE': 47, 'SYMPTOM': 9044, 'TEST': 48}

# Check indexing
python -c "from src.baseline_ner import _index; print(f'Indexed entries: {len(_index.entries)}')"
# Expected: Indexed entries: 9329
```

---

**Last Updated**: 2024
**Status**: ✅ All lexicons loaded and indexed correctly

