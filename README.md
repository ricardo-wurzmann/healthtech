# HealthTech - Clinical NLP Pipeline

A clinical Natural Language Processing (NLP) pipeline for extracting structured information from Portuguese clinical texts (prontuários). The pipeline processes clinical cases, extracts medical entities, classifies assertions, and outputs structured JSON data.

## Overview

The pipeline performs the following tasks:
1. **Text Ingestion**: Loads clinical cases from JSON files or PDFs
2. **Text Preprocessing**: Normalizes whitespace, punctuation, and formatting
3. **Sentence Segmentation**: Splits text into sentences using spaCy
4. **Named Entity Recognition (NER)**: Extracts medical entities using patterns + lexicon-based matching
5. **Assertion Classification**: Classifies entity assertions as PRESENT, NEGATED, POSSIBLE, or HISTORICAL
6. **Entity Filtering**: Removes junk predictions (stopwords, invalid spans, non-nucleus symptoms)
7. **Output Generation**: Produces structured JSON with entities, spans, and metadata

## Architecture

```
Input (JSON/PDF)
    ↓
[ingest_json.py / ingest.py] → Document objects
    ↓
[preprocess.py] → Normalized text
    ↓
[segment.py] → Sentences with offsets
    ↓
[baseline_ner.py] → Entity spans
    ├─ [patterns.py] → High-precision regex patterns
    ├─ [search_index.py] → Fast lexicon matching
    └─ [lexicon.py] → Medical term dictionary
    ↓
[context.py] → Assertion classification
    ↓
[postprocess/filters.py] → Filter junk entities
    ↓
[schema.py] → Structured output
    ↓
[run_pipeline.py] → JSON files
```

## Project Structure

```
nlp_clin/
├── src/
│   ├── run_pipeline.py      # Main pipeline orchestrator
│   ├── ingest_json.py        # JSON case loader
│   ├── ingest.py             # PDF loader (legacy)
│   ├── preprocess.py         # Text normalization
│   ├── segment.py            # Sentence segmentation
│   ├── search_index.py       # Lexicon indexing for fast matching
│   ├── baseline_ner.py       # Entity extraction engine
│   ├── patterns.py           # High-precision regex patterns (vitals, GCS)
│   ├── lexicon.py            # Medical term dictionary
│   ├── context.py            # Assertion classification
│   ├── postprocess/          # Post-processing modules
│   │   ├── __init__.py
│   │   └── filters.py        # Entity filtering (removes junk)
│   ├── schema.py             # Data models
│   ├── eval/                 # Evaluation framework
│   │   ├── __init__.py
│   │   ├── schema.py         # Gold/Pred data models
│   │   ├── create_gold_template.py  # Template generation
│   │   ├── matching.py       # Entity matching logic
│   │   ├── metrics.py        # Metrics computation
│   │   ├── evaluate.py       # Main evaluation CLI
│   │   └── report.py         # Report printing
│   ├── linking.py            # (Future) Entity linking to ontologies
│   ├── coding_icd10.py       # (Future) ICD-10 coding
│   └── ner.py                # (Future) Advanced NER models
├── data/
│   ├── raw/                  # Input files (JSON/PDF)
│   └── processed/            # Output files
│       └── cases/            # Per-case JSON outputs
└── tests/                    # Unit tests
    └── test_eval_matching.py # Evaluation matching tests
```

## File Descriptions

### Core Pipeline Files

#### `run_pipeline.py`
**Main entry point** for the pipeline. Orchestrates the entire processing workflow:
- Parses command-line arguments
- Loads documents (JSON or PDF)
- Processes each document through the pipeline stages
- Writes output JSON files (one per case for JSON input)
- Supports both JSON multi-case and legacy PDF single-document modes

**Key functions:**
- `run_on_json()`: Processes JSON files with multiple cases
- `run_on_pdf()`: Legacy PDF processing (backward compatibility)
- `process_document()`: Core processing function for a single document

#### `ingest_json.py`
**JSON case loader** for multi-case input files:
- Loads JSON array containing multiple clinical cases
- Extracts `case_id`, `group`, and `raw_text` from each case
- Falls back to structured fields (`qd`, `hpma`, `isda`, `ap`, `af`) if `raw_text` is missing
- Creates `Document` objects with metadata (`case_id`, `group`)
- Generates document IDs as `{stem}_case_{case_id:04d}`

**Key functions:**
- `load_json_cases()`: Main loader function
- `_reconstruct_text_from_structured()`: Fallback text reconstruction

#### `ingest.py`
**PDF loader** (legacy support):
- Extracts text from PDF files using PyPDF
- Handles null bytes and page concatenation
- Creates basic `Document` objects (without `case_id`/`group`)

**Key functions:**
- `load_pdf_as_document()`: Loads a PDF file
- `extract_text_from_pdf()`: Extracts text from PDF pages

### Text Processing Files

#### `preprocess.py`
**Text normalization** module:
- Normalizes line endings (CRLF → LF)
- Collapses multiple spaces and newlines
- Standardizes punctuation spacing
- Formats common clinical patterns (e.g., "120x70" → "120 x 70" for blood pressure)
- **Preserves accents** in the output (only normalizes for internal processing)

**Key function:**
- `normalize_text()`: Main normalization function

#### `segment.py`
**Sentence segmentation** using spaCy:
- Uses Portuguese spaCy model (`pt_core_news_sm`)
- Disables unnecessary components (tagger, parser, NER, lemmatizer) for speed
- Adds `sentencizer` component to set sentence boundaries
- Returns sentences with character offsets relative to original text

**Key classes/functions:**
- `Sentence`: Dataclass with `text`, `start`, `end` offsets
- `split_sentences()`: Main segmentation function

### Entity Extraction Files

#### `search_index.py`
**Fast lexicon indexing** for efficient entity matching:
- Builds a normalized token-based index from the lexicon
- Normalizes terms: lowercase, remove accents, collapse whitespace, strip punctuation
- Tokenizes terms into words
- Creates inverted index: token → list of lexicon entries
- Separates single-token vs multi-token entries for optimized matching
- Supports three matching strategies: exact, token-based, and fuzzy

**Key classes:**
- `LexiconIndex`: Main indexing class
- `LexiconEntry`: Normalized lexicon entry with tokens
- `MatchCandidate`: Candidate match from lexicon

**Key methods:**
- `find_candidates()`: Generates exact and token-based candidates
- `find_fuzzy_candidates()`: Generates fuzzy candidates (fallback)

#### `baseline_ner.py`
**Entity extraction engine** using layered retrieval:
- **Layer 1**: Regex patterns (high precision, e.g., vitals/GCS/FAST)
- **Layer 2**: Exact phrase matches from lexicon
- **Layer 3**: Token-based matching:
  - Single-token terms: whole word matching with boundaries
  - Multi-token terms: requires all tokens present, then confirms with substring
- **Layer 4**: Fuzzy matching (only if no exact/token matches found, excludes SYMPTOM)
- **Overlap resolution**: Intelligently resolves overlapping spans (prefers longer spans, higher scores)
- Maps normalized matches back to original text (handles accents)

**Key classes:**
- `EntitySpan`: Extracted entity with span, type, score, and sentence context

**Key functions:**
- `extract_entities_baseline()`: Main extraction function
- `_find_span_in_original()`: Maps normalized matches to original text
- `_resolve_overlaps()`: Resolves overlapping entity spans

#### `patterns.py`
**High-precision regex patterns**:
- Captures vitals (PA, FC, FR, SpO2) and Glasgow/GCS
- Emits type `TEST` (and `PROCEDURE` for FAST)

#### `lexicon.py`
**Medical term dictionary**:
- Defines entity types: `SYMPTOM`, `PROBLEM`, `TEST`, `DRUG`, `PROCEDURE`, `ANATOMY`
- Contains Portuguese clinical terms with their entity types
- Currently includes: symptoms (vômito, náusea, dor epigástrica, febre, etc.), tests (hemograma, cultura de urina, etc.), drugs (cefadroxila, dipirona, paracetamol), and procedures (FAST)

**Structure:**
- `LEXICON`: List of `(term, entity_type)` tuples

### Context Classification Files

#### `context.py`
**Assertion classification** using rule-based patterns:
- Classifies entity assertions into four categories:
  - **PRESENT**: Default (no negation/uncertainty markers)
  - **NEGATED**: Contains negation patterns (nega, negou, sem, não tem, etc.)
  - **POSSIBLE**: Contains uncertainty patterns (suspeita, hipótese, possível, provável)
  - **HISTORICAL**: Contains historical markers (história de, antecedentes, passado, HPP)

**Key function:**
- `classify_assertion()`: Classifies a sentence containing an entity

### Data Model Files

#### `schema.py`
**Data models** for input/output:
- `LinkCandidate`: Entity linking candidate (system, code, label, score)
- `EntityOut`: Output entity with span, offsets, type, score, assertion, evidence, links, ICD-10 codes
- `DocOut`: Complete document output with doc_id, source, text, entities, case_id, group

### Future/Placeholder Files

#### `linking.py`
**Future**: Entity linking to medical ontologies (SNOMED CT, UMLS, etc.)

#### `coding_icd10.py`
**Future**: Automatic ICD-10 coding for extracted entities

#### `ner.py`
**Future**: Advanced NER models (transformer-based, BERT, etc.)

## Usage

### Processing JSON Cases (Recommended)

```bash
# Process JSON file with multiple cases (run from nlp_clin/ directory)
python -m src.run_pipeline --input data/raw/pepv1.json --out_dir data/processed/cases

# Using default values
python -m src.run_pipeline  # Uses data/raw/pepv1.json and data/processed/cases

# Alternative: run directly (from nlp_clin/src/ directory)
python run_pipeline.py --input ../data/raw/pepv1.json --out_dir ../data/processed/cases
```

**Note:** The pipeline now runs as a Python package. Use `python -m src.run_pipeline` from the `nlp_clin/` directory for best results.

**Input JSON format:**
```json
[
  {
    "case_id": 1,
    "group": "prontuario",
    "raw_text": "Paciente apresenta dor epigástrica e vômitos..."
  },
  {
    "case_id": 2,
    "group": "caso_estruturado",
    "raw_text": "..."
  }
]
```

**Output:** One JSON file per case in the output directory:
- `pepv1_case_0001.json`
- `pepv1_case_0002.json`
- etc.

**Combine predictions for evaluation:**
```bash
# Combine individual case files into single predictions.json
python combine_predictions.py data/processed/cases data/processed/predictions.json
```

### Legacy PDF Mode

```bash
python -m src.run_pipeline --input data/raw/document.pdf --out data/processed/output.json
```

## Output Format

Each output JSON file contains:

```json
{
  "doc_id": "pepv1_case_0001",
  "source": "data/raw/pepv1.json",
  "text": "Normalized clinical text...",
  "entities": [
    {
      "span": "dor epigástrica",
      "start": 150,
      "end": 167,
      "type": "SYMPTOM",
      "score": 0.99,
      "assertion": "PRESENT",
      "evidence": "Paciente apresenta dor epigástrica intensa...",
      "links": [],
      "icd10": []
    }
  ],
  "case_id": 1,
  "group": "prontuario"
}
```

**Entity fields:**
- `span`: Extracted text (preserves original accents)
- `start`/`end`: Character offsets in original text
- `type`: Entity type (SYMPTOM, TEST, DRUG, PROCEDURE, etc.)
- `score`: Confidence score (0.0-1.0)
- `assertion`: PRESENT, NEGATED, POSSIBLE, or HISTORICAL
- `evidence`: Full sentence containing the entity
- `links`: (Future) Links to medical ontologies
- `icd10`: (Future) ICD-10 codes

## Dependencies

Required Python packages:
- `spacy` + `pt_core_news_sm` model (Portuguese spaCy model)
- `rapidfuzz` (fuzzy string matching)
- `unidecode` (accent removal for normalization)
- `pypdf` (PDF processing, legacy mode)

Install spaCy Portuguese model:
```bash
python -m spacy download pt_core_news_sm
```

## Pipeline Stages Explained

### 1. Ingestion
- **JSON mode**: Loads multiple cases, extracts metadata
- **PDF mode**: Extracts text from PDF pages

### 2. Preprocessing
- Normalizes whitespace and line breaks
- Standardizes punctuation spacing
- Formats clinical patterns (blood pressure, etc.)
- **Important**: Original text with accents is preserved in output

### 3. Sentence Segmentation
- Uses spaCy sentencizer for Portuguese
- Returns sentences with character-level offsets
- Offsets are relative to the original (normalized) text

### 4. Entity Extraction (Layered Strategy)

**Step 1: Regex Patterns**
- High-precision patterns for specific entities (e.g., "FAST" procedure)
- Score: 0.95

**Step 2: Exact Phrase Matching**
- Normalizes both lexicon terms and sentences
- Finds exact substring matches
- Score: 0.99

**Step 3: Token-Based Matching**
- Single-token terms: whole word matching with word boundaries
- Multi-token terms: requires all tokens present, then confirms phrase
- Score: 0.95

**Step 4: Fuzzy Matching (Fallback)**
- Only runs if no exact/token matches found
- Uses rapidfuzz for similarity scoring
- Compares against sentence n-grams
- Score: similarity ratio / 100.0

**Step 5: Overlap Resolution**
- Removes duplicate spans (same start/end/type)
- Resolves overlaps: prefers longer spans, higher scores
- Keeps best entity when spans overlap significantly (>50%)

### 5. Assertion Classification
- Analyzes sentence context for each entity
- Rule-based patterns for negation, uncertainty, historical
- Default: PRESENT

### 6. Entity Filtering
- **Span integrity**: Removes entities with invalid offsets or empty spans
- **Minimum length**: Filters spans shorter than 4 characters or without alphabetic characters
- **Stopword-only spans**: Removes entities where all tokens are Portuguese stopwords (e.g., "com", "relatando", "à palpação do")
- **SYMPTOM nucleus constraint**: SYMPTOM entities must contain at least one clinical nucleus token (e.g., "dor", "cefaleia", "febre")
- **Punctuation trimming**: Optionally trims leading/trailing punctuation and adjusts offsets
- Logs filtering statistics per document

### 7. Output Generation
- Creates structured JSON per case
- Includes all entities with metadata
- Preserves original text with accents
- Character offsets refer to original text

## Performance Optimizations

1. **Lexicon Indexing**: Token-based inverted index for fast candidate generation
2. **Layered Matching**: Exact matches first, fuzzy only as fallback
3. **Sentence-Level Processing**: Entities matched within sentences, not entire document
4. **SpaCy Optimization**: Disables unnecessary components (tagger, parser, NER, lemmatizer)
5. **Overlap Resolution**: Efficient deduplication algorithm

## Extending the Pipeline

### Adding New Lexicon Terms

Edit `src/lexicon.py`:
```python
LEXICON = [
    # ... existing terms ...
    ("novo_termo", "ENTITY_TYPE"),
]
```

### Adding Regex Patterns

Edit `src/patterns.py`:
```python
PATTERN_DEFS = [
    (re.compile(r"\bSEU_PADRAO\b", re.IGNORECASE), "TYPE", 0.95),
]
```

### Adding Assertion Patterns

Edit `src/context.py`:
```python
NEG_PATTERNS = [
    # ... existing patterns ...
    r"\bnovo_padrao\b",
]
```

### Customizing Entity Filtering

Edit `src/postprocess/filters.py`:
```python
# Add stopwords
DEFAULT_STOPWORDS.add("novo_stopword")

# Add symptom nucleus tokens
DEFAULT_SYMPTOM_NUCLEUS.add("novo_sintoma")

# Or create custom FilterConfig
from src.postprocess.filters import FilterConfig, filter_entities

config = FilterConfig(
    min_chars=5,
    apply_to_types={"SYMPTOM", "TEST"},  # Filter multiple types
    trim_punct=False
)
```

## Audit Scripts

Use these to inspect intermediate outputs quickly:

```bash
# From repo root
python nlp_clin/audit/show_preprocess.py --case_id 1
python nlp_clin/audit/show_segments.py --case_id 1
python nlp_clin/audit/show_pipeline_case.py --case_id 1 --n_sent 30
```

## Testing

Unit tests are located in `tests/` directory:
- `test_matching.py`: Tests for entity matching (containment, min_cov, tie-breaking)
- `test_filters.py`: Tests for entity filtering rules
- `test_eval_matching.py`: Evaluation matching tests

Run tests:
```bash
# From repo root
PYTHONPATH="nlp_clin/src" pytest nlp_clin/tests

# Or from nlp_clin/ directory
python -m pytest tests/
# Or
python -m unittest discover tests
```

Test coverage includes:
- Exact match extraction
- Token-based multi-word matching
- Overlap resolution
- Assertion classification
- Text normalization
- Entity filtering (stopwords, nucleus, length)
- Matching modes (IoU, min_cov, containment)

## Evaluation Framework

The pipeline includes a comprehensive evaluation framework for assessing NER and assertion classification performance.

### Overview

The evaluation framework provides:
- **Gold annotation template generation**: Create annotation templates from input cases or predictions
- **Strict and relaxed matching**: Exact span matching or overlap-based matching (IoU or overlap ratio)
- **Comprehensive metrics**: NER precision/recall/F1 (overall and per-type), assertion accuracy, coverage statistics
- **Error analysis**: False positives, false negatives, and assertion mismatches with examples

### Quick Start

#### 1. Create Gold Annotation Template

Generate a template file for manual annotation (run from `nlp_clin/` directory):

```bash
# From input cases
python create_gold_template.py data/raw/pepv1.json data/gold/template.jsonl

# From pipeline predictions (prefilled with predicted entities)
python create_gold_template.py --from-predictions data/processed/cases/pepv1_case_0001.json data/gold/template.jsonl

# Prefill template with predictions for easier annotation
python create_gold_template.py data/raw/pepv1.json data/gold/template.jsonl --prefill data/processed/predictions.json
```

**Gold Format (JSONL):**
Each line is a case with gold annotations:
```json
{
  "case_id": "1",
  "group": "prontuario",
  "raw_text": "Paciente apresenta dor epigástrica...",
  "gold_entities": [
    {
      "start": 20,
      "end": 35,
      "text": "dor epigástrica",
      "type": "SYMPTOM",
      "assertion": "PRESENT",
      "notes": ""
    }
  ],
  "metadata": {"annotator": "user1", "version": "v1"}
}
```

#### 2. Auto-fill Offsets (Recommended)

Before running the evaluation, auto-fill missing `start` / `end` offsets in your gold file
based on `raw_text` (run from `nlp_clin/` directory):

```bash
python -m eval.fill_offsets \
  --gold data/gold/template.jsonl \
  --out data/gold/template.with_offsets.jsonl \
  --report data/gold/offset_fill_report.json
```

This script:
- Keeps existing offsets unchanged
- Fills offsets when there is a **unique** robust match in `raw_text` (case-insensitive, accent-insensitive, whitespace-tolerant)
- Marks ambiguous or not-found entities in `offset_fill_report.json` without guessing

You can optionally allow best-effort filling for ambiguous matches:

```bash
python -m eval.fill_offsets \
  --gold data/gold/template.jsonl \
  --out data/gold/template.with_offsets.jsonl \
  --report data/gold/offset_fill_report.json \
  --allow-ambiguous-best-effort
```

#### 3. Run Evaluation

Evaluate predictions against gold standard (run from `nlp_clin/` directory):

```bash
# Strict matching (exact start/end/type)
python evaluate.py --pred data/processed/predictions.json --gold data/gold/template.with_offsets.jsonl --out reports/report.json

# Relaxed matching (overlap-based) with IoU
python evaluate.py --pred data/processed/predictions.json --gold data/gold/template.with_offsets.jsonl --out reports/report.json --relaxed --overlap 0.5

# Use overlap/min_length ratio instead of IoU
python evaluate.py --pred predictions.json --gold data/gold/template.with_offsets.jsonl --out report.json --relaxed --overlap 0.5 --no-iou

# Advanced matching modes (recommended for clinical spans)
# Containment and min_cov help match cases like "cefaleia" (pred) inside "cefaleia intensa" (gold)
python evaluate.py --pred data/processed/predictions.json --gold data/gold/template.with_offsets.jsonl --out report.json --relaxed --overlap 0.5 --match-mode iou_or_min_cov_or_containment
```

#### 4. View Report

Print a readable summary of the evaluation (run from `nlp_clin/` directory):

```bash
python report.py --report reports/report.json

# Skip error examples
python report.py --report reports/report.json --no-errors
```

### Evaluation Metrics

#### NER Metrics
- **Overall**: Precision, Recall, F1, TP/FP/FN counts
- **Per-Type**: Metrics broken down by entity type (SYMPTOM, TEST, DRUG, etc.)

#### Assertion Metrics
- **Accuracy**: Percentage of correctly classified assertions
- **Confusion Matrix**: Detailed breakdown of assertion classification errors

#### Coverage Metrics
- Cases with/without entities
- Average entities per case
- Entity type distribution
- Top frequent entity texts

#### Error Analysis
- **False Positives**: Predicted entities not in gold standard
- **False Negatives**: Gold entities not predicted
- **Assertion Mismatches**: Entities matched but with wrong assertion label

### Matching Strategies

#### Strict Matching (Default)
Requires:
- Exact same start offset
- Exact same end offset
- Same entity type (after normalization)

#### Relaxed Matching
Requires:
- Overlap >= threshold (configurable, default 0.5)
- Same entity type (after normalization)

**Matching Modes** (controlled by `--match-mode` flag):

1. **`iou`** (default): Uses IoU (Intersection over Union) only
   - Formula: `overlap / (span1 + span2 - overlap)`

2. **`iou_or_min_cov`**: Matches if IoU >= threshold OR min coverage >= threshold
   - Min coverage: `overlap / min(span1_length, span2_length)`
   - Useful when one span is much shorter than the other

3. **`iou_or_containment`**: Matches if IoU >= threshold OR one span contains the other
   - Containment: `(P.start >= G.start and P.end <= G.end)` OR `(G.start >= P.start and G.end <= P.end)`
   - Useful for cases like "cefaleia" (pred) inside "cefaleia intensa" (gold)

4. **`iou_or_min_cov_or_containment`** (recommended for clinical notes): Matches if ANY condition is true
   - Combines all three strategies for maximum recall
   - Default when `--relaxed` is used (unless `--no-iou` is set)

**Legacy option:**
- `--no-iou`: Uses overlap/min_length ratio instead of IoU (deprecated, use `--match-mode` instead)

### Label Normalization

Entity type labels are automatically normalized to handle synonyms:
- `DIAGNOSIS`, `DISEASE`, `CONDITION` → `PROBLEM`
- `SIGN` → `SYMPTOM`
- `EXAM`, `EXAMINATION` → `TEST`
- `MEDICATION`, `MEDICINE` → `DRUG`
- `BODY_PART` → `ANATOMY`

### Report Output

The evaluation generates a JSON report with:
```json
{
  "config": {
    "relaxed_matching": false,
    "overlap_threshold": 0.5,
    "match_mode": "iou_or_min_cov_or_containment",
    "matched_by_iou": 120,
    "matched_by_min_cov": 15,
    "matched_by_containment": 8,
    "total_cases": 100
  },
  "ner": {
    "overall": {"precision": 0.85, "recall": 0.78, "f1": 0.81, ...},
    "per_type": {
      "SYMPTOM": {"precision": 0.90, "recall": 0.85, "f1": 0.87, ...},
      ...
    }
  },
  "assertion": {
    "accuracy": 0.92,
    "confusion_matrix": {...}
  },
  "coverage": {...},
  "errors": {
    "false_positives": [...],
    "false_negatives": [...],
    "assertion_mismatches": [...]
  }
}
```

### Example Output

```
======================================================================
EVALUATION REPORT
======================================================================

Configuration:
  Matching: Strict
  Total cases evaluated: 50

======================================================================
NER EVALUATION SUMMARY
======================================================================

Overall Metrics:
  Precision: 0.852
  Recall:    0.783
  F1 Score:  0.816

Counts:
  True Positives:  156
  False Positives: 27
  False Negatives: 43

Per-Type Metrics:
  Type            Precision    Recall       F1           TP     FP     FN
  --------------- ------------ ------------ ------------ ------ ------ ------
  SYMPTOM         0.900        0.850        0.874        51     6      9
  TEST            0.820        0.750        0.783        41     9      14
  DRUG            0.880        0.920        0.900        44     6      4
  ...

======================================================================
ASSERTION CLASSIFICATION SUMMARY
======================================================================

Accuracy: 0.923
Total Matched Entities: 156

Confusion Matrix:
  Gold\Pred      PRESENT      NEGATED      POSSIBLE     HISTORICAL
  --------------- ------------ ------------ ------------ ------------
  PRESENT         112          3            2            1
  NEGATED         5           28          0            0
  ...
```

### Best Practices

1. **Annotation Guidelines**:
   - Use consistent entity boundaries (include determiners/adjectives when part of the medical term)
   - Mark assertion labels carefully (PRESENT is default if uncertain)
   - Add notes for ambiguous cases

2. **Evaluation Strategy**:
   - Start with strict matching for precise evaluation
   - Use relaxed matching to understand boundary issues
   - Compare both to get a complete picture

3. **Iterative Improvement**:
   - Review false positives to identify lexicon issues
   - Review false negatives to find missing terms
   - Analyze assertion mismatches to improve context rules

### File Structure

```
src/eval/
├── __init__.py              # Package initialization
├── schema.py                # Data models (GoldCase, PredCase, etc.)
├── create_gold_template.py  # Template generation CLI
├── matching.py              # Entity matching logic
├── metrics.py               # Metrics computation
├── evaluate.py              # Main evaluation CLI
└── report.py                # Report printing
```

## Future Enhancements

- **Entity Linking** (`linking.py`): Link entities to SNOMED CT, UMLS, etc.
- **ICD-10 Coding** (`coding_icd10.py`): Automatic diagnosis coding
- **Advanced NER** (`ner.py`): Transformer-based models (BERT, ClinicalBERT)
- **Relation Extraction**: Extract relationships between entities
- **Temporal Reasoning**: Handle temporal expressions and timelines

## License

[Add your license here]

## Contributors

[Add contributors here]
