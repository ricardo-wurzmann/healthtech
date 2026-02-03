import csv
import json
import logging
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import pdfplumber


BASE_DIR = Path(__file__).resolve().parents[1]
RAW_PDF_DIR = BASE_DIR / "nlp_clin" / "data" / "vocab" / "raw_pdfs"
STAGING_DIR = BASE_DIR / "nlp_clin" / "data" / "vocab" / "staging"
QA_DIR = BASE_DIR / "nlp_clin" / "data" / "vocab" / "qa"


LOG = logging.getLogger("extract_all_pdfs")

CID10_CODE_RE = re.compile(r"^[A-Z][0-9]{2}(?:\.[0-9A-Z]{1,4})?$")
TUSS_CODE_RE = re.compile(r"^\d{8}$")
ABBREV_RE = re.compile(r"^[A-Z0-9/().+\-]{1,12}$")

SIGLARIO_ALLOWED_PAGES = (17, 60)
SIGLARIO_PROHIBITED_PAGES = (11, 14)
SIGLARIO_AMBIGUOUS_PAGES = (15, 16)


def normalize_cell(value: str) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value).replace("\n", " ")).strip()


def is_header_like(text: str) -> bool:
    if not text:
        return True
    lowered = text.lower()
    header_tokens = ["sigla", "abrevia", "significado", "descricao", "descrição"]
    return any(token in lowered for token in header_tokens)


def split_abbrev_meaning(line: str):
    line = normalize_cell(line)
    if not line:
        return None, None
    if "|" in line:
        parts = [p.strip() for p in line.split("|") if p.strip()]
        if len(parts) >= 2:
            return parts[0], " ".join(parts[1:])
    multi_space = re.split(r"\s{2,}", line)
    if len(multi_space) >= 2:
        return multi_space[0].strip(), " ".join(p.strip() for p in multi_space[1:] if p.strip())
    for sep in [" - ", " – ", " — "]:
        if sep in line:
            left, right = line.split(sep, 1)
            return left.strip(), right.strip()
    match = re.match(r"^([A-Z0-9/().+\-]{1,12})\s+(.*)$", line)
    if match:
        return match.group(1).strip(), match.group(2).strip()
    return None, None


def extract_tables(page):
    settings_candidates = [
        {
            "vertical_strategy": "lines",
            "horizontal_strategy": "lines",
            "intersection_tolerance": 5,
            "snap_tolerance": 3,
            "join_tolerance": 3,
        },
        {
            "vertical_strategy": "text",
            "horizontal_strategy": "text",
            "intersection_tolerance": 5,
            "snap_tolerance": 3,
            "join_tolerance": 3,
        },
    ]
    for settings in settings_candidates:
        tables = page.extract_tables(settings)
        if tables:
            return tables
    return []


def iter_page_lines(page):
    tables = extract_tables(page)
    for table in tables:
        for row in table:
            cleaned = [normalize_cell(cell) for cell in row if normalize_cell(cell)]
            if cleaned:
                yield " ".join(cleaned)
    text = page.extract_text() or ""
    for line in text.splitlines():
        cleaned = normalize_cell(line)
        if cleaned:
            yield cleaned


def write_csv(path: Path, fieldnames, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def dedupe_rows(rows, key_fields):
    seen = set()
    unique = []
    for row in rows:
        key = tuple(row.get(field, "").strip() for field in key_fields)
        if key in seen:
            continue
        seen.add(key)
        unique.append(row)
    return unique


def add_warning(warnings, file_key, message, sample):
    warnings.append({"file": file_key, "message": message, "sample": sample})


def validate_text(warnings, file_key, label, text):
    if not text or len(text) < 2:
        add_warning(warnings, file_key, f"{label} too short", text)
    if len(text) > 200:
        add_warning(warnings, file_key, f"{label} too long", text[:200])


def extract_code_name_pdf(pdf_path: Path, code_re: re.Pattern, file_key: str, warnings):
    results = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            for line in iter_page_lines(page):
                if is_header_like(line):
                    continue
                match = re.match(r"^(\S+)\s+(.*)$", line)
                if not match:
                    continue
                raw_code, raw_name = match.group(1).strip(), match.group(2).strip()
                if not code_re.match(raw_code):
                    continue
                validate_text(warnings, file_key, "name", raw_name)
                results.append((raw_code, raw_name))
    return results


def extract_siglario_allowed(pdf_path: Path, warnings):
    start, end = SIGLARIO_ALLOWED_PAGES
    results = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_number in range(start - 1, end):
            page = pdf.pages[page_number]
            tables = extract_tables(page)
            extracted = False
            for table in tables:
                for row in table:
                    cleaned = [normalize_cell(cell) for cell in row]
                    if not cleaned or all(not cell for cell in cleaned):
                        continue
                    if len(cleaned) >= 2:
                        abbrev = cleaned[0]
                        meaning = " ".join(cell for cell in cleaned[1:] if cell)
                        if not abbrev or not meaning:
                            continue
                        if len(abbrev) == 1 and abbrev.isalpha():
                            continue
                        if not ABBREV_RE.match(abbrev):
                            continue
                        validate_text(warnings, "siglario_allowed", "meaning", meaning)
                        results.append((abbrev, meaning))
                        extracted = True
            if extracted:
                continue
            text = page.extract_text() or ""
            for line in text.splitlines():
                if is_header_like(line):
                    continue
                abbrev, meaning = split_abbrev_meaning(line)
                if not abbrev or not meaning:
                    continue
                if len(abbrev) == 1 and abbrev.isalpha():
                    continue
                if not ABBREV_RE.match(abbrev):
                    continue
                validate_text(warnings, "siglario_allowed", "meaning", meaning)
                results.append((abbrev, meaning))
    return results


def extract_siglario_prohibited(pdf_path: Path, warnings):
    start, end = SIGLARIO_PROHIBITED_PAGES
    results = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_number in range(start - 1, end):
            page = pdf.pages[page_number]
            tables = extract_tables(page)
            for table in tables:
                for row in table:
                    cleaned = [normalize_cell(cell) for cell in row]
                    if not cleaned or all(not cell for cell in cleaned):
                        continue
                    if any(is_header_like(cell) for cell in cleaned):
                        continue
                    if len(cleaned) < 3:
                        continue
                    abbrev = cleaned[0]
                    incorrect = cleaned[1] if len(cleaned) >= 2 else ""
                    danger = cleaned[2] if len(cleaned) >= 3 else ""
                    recommended = cleaned[3] if len(cleaned) >= 4 else ""
                    if not abbrev or not ABBREV_RE.match(abbrev):
                        continue
                    validate_text(warnings, "siglario_prohibited", "incorrect", incorrect)
                    results.append((abbrev, incorrect, danger, recommended))
            if not tables:
                text = page.extract_text() or ""
                for line in text.splitlines():
                    if is_header_like(line):
                        continue
                    parts = [p.strip() for p in line.split("|") if p.strip()]
                    if len(parts) < 3:
                        continue
                    abbrev = parts[0]
                    if not ABBREV_RE.match(abbrev):
                        continue
                    incorrect = parts[1] if len(parts) >= 2 else ""
                    danger = parts[2] if len(parts) >= 3 else ""
                    recommended = parts[3] if len(parts) >= 4 else ""
                    validate_text(warnings, "siglario_prohibited", "incorrect", incorrect)
                    results.append((abbrev, incorrect, danger, recommended))
    return results


def extract_siglario_ambiguous(pdf_path: Path, warnings):
    start, end = SIGLARIO_AMBIGUOUS_PAGES
    results = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_number in range(start - 1, end):
            page = pdf.pages[page_number]
            tables = extract_tables(page)
            for table in tables:
                for row in table:
                    cleaned = [normalize_cell(cell) for cell in row]
                    if not cleaned or all(not cell for cell in cleaned):
                        continue
                    if any(is_header_like(cell) for cell in cleaned):
                        continue
                    if len(cleaned) < 2:
                        continue
                    abbrev = cleaned[0]
                    meaning_1 = cleaned[1] if len(cleaned) >= 2 else ""
                    meaning_2 = cleaned[2] if len(cleaned) >= 3 else ""
                    context = cleaned[3] if len(cleaned) >= 4 else ""
                    if not abbrev or not ABBREV_RE.match(abbrev):
                        continue
                    validate_text(warnings, "siglario_ambiguous", "meaning", meaning_1)
                    results.append((abbrev, meaning_1, meaning_2, context))
            if not tables:
                text = page.extract_text() or ""
                for line in text.splitlines():
                    if is_header_like(line):
                        continue
                    parts = [p.strip() for p in line.split("|") if p.strip()]
                    if len(parts) < 2:
                        continue
                    abbrev = parts[0]
                    if not ABBREV_RE.match(abbrev):
                        continue
                    meaning_1 = parts[1] if len(parts) >= 2 else ""
                    meaning_2 = parts[2] if len(parts) >= 3 else ""
                    context = parts[3] if len(parts) >= 4 else ""
                    validate_text(warnings, "siglario_ambiguous", "meaning", meaning_1)
                    results.append((abbrev, meaning_1, meaning_2, context))
    return results


def extract_labs(pdf_path: Path, warnings):
    results = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            tables = extract_tables(page)
            for table in tables:
                for row in table:
                    cleaned = [normalize_cell(cell) for cell in row]
                    if not cleaned or all(not cell for cell in cleaned):
                        continue
                    if any(is_header_like(cell) for cell in cleaned):
                        continue
                    name = cleaned[0]
                    unit = cleaned[1] if len(cleaned) >= 2 else ""
                    method = cleaned[2] if len(cleaned) >= 3 else ""
                    if not name:
                        continue
                    validate_text(warnings, "labs", "name", name)
                    results.append((name, unit, method))
            if not tables:
                text = page.extract_text() or ""
                for line in text.splitlines():
                    if is_header_like(line):
                        continue
                    parts = [p.strip() for p in line.split("|") if p.strip()]
                    if not parts:
                        continue
                    name = parts[0]
                    unit = parts[1] if len(parts) >= 2 else ""
                    method = parts[2] if len(parts) >= 3 else ""
                    validate_text(warnings, "labs", "name", name)
                    results.append((name, unit, method))
    return results


def extract_generic_terms(pdf_path: Path, warnings, file_key):
    results = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            for line in iter_page_lines(page):
                if is_header_like(line):
                    continue
                cleaned = normalize_cell(line)
                if len(cleaned) < 2:
                    continue
                validate_text(warnings, file_key, "term", cleaned)
                results.append(cleaned)
    return results


def ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )

    if not RAW_PDF_DIR.exists():
        LOG.error("Raw PDF directory not found: %s", RAW_PDF_DIR)
        sys.exit(1)

    ensure_dir(STAGING_DIR)
    ensure_dir(QA_DIR)

    warnings = []
    summary = defaultdict(dict)

    LOG.info("Starting PDF extraction in %s", RAW_PDF_DIR)

    # Siglario (start with allowed section per requirement)
    siglario_path = RAW_PDF_DIR / "siglarario1.pdf"
    if siglario_path.exists():
        LOG.info("Extracting siglario allowed abbreviations (pages %s-%s)", *SIGLARIO_ALLOWED_PAGES)
        allowed_rows = extract_siglario_allowed(siglario_path, warnings)
        allowed_rows = dedupe_rows(
            [
                {
                    "abbreviation": abbrev,
                    "meaning": meaning,
                    "status": "allowed",
                    "source": siglario_path.name,
                    "version": "2021",
                }
                for abbrev, meaning in allowed_rows
            ],
            ["abbreviation", "meaning"],
        )
        write_csv(
            STAGING_DIR / "siglario_allowed_raw.csv",
            ["abbreviation", "meaning", "status", "source", "version"],
            allowed_rows,
        )
        summary["siglario_allowed_raw.csv"]["count"] = len(allowed_rows)

        LOG.info("Extracting siglario prohibited abbreviations (pages %s-%s)", *SIGLARIO_PROHIBITED_PAGES)
        prohibited_rows = extract_siglario_prohibited(siglario_path, warnings)
        prohibited_rows = dedupe_rows(
            [
                {
                    "abbreviation": abbrev,
                    "incorrect_meaning": incorrect,
                    "danger_reason": danger,
                    "recommended_form": recommended,
                    "status": "prohibited",
                    "source": siglario_path.name,
                    "version": "2021",
                }
                for abbrev, incorrect, danger, recommended in prohibited_rows
            ],
            ["abbreviation", "incorrect_meaning", "recommended_form"],
        )
        write_csv(
            STAGING_DIR / "siglario_prohibited_raw.csv",
            [
                "abbreviation",
                "incorrect_meaning",
                "danger_reason",
                "recommended_form",
                "status",
                "source",
                "version",
            ],
            prohibited_rows,
        )
        summary["siglario_prohibited_raw.csv"]["count"] = len(prohibited_rows)

        LOG.info("Extracting siglario ambiguous abbreviations (pages %s-%s)", *SIGLARIO_AMBIGUOUS_PAGES)
        ambiguous_rows = extract_siglario_ambiguous(siglario_path, warnings)
        ambiguous_rows = dedupe_rows(
            [
                {
                    "abbreviation": abbrev,
                    "meaning_1": meaning_1,
                    "meaning_2": meaning_2,
                    "context_required": context,
                    "status": "ambiguous",
                    "source": siglario_path.name,
                    "version": "2021",
                }
                for abbrev, meaning_1, meaning_2, context in ambiguous_rows
            ],
            ["abbreviation", "meaning_1", "meaning_2", "context_required"],
        )
        write_csv(
            STAGING_DIR / "siglario_ambiguous_raw.csv",
            [
                "abbreviation",
                "meaning_1",
                "meaning_2",
                "context_required",
                "status",
                "source",
                "version",
            ],
            ambiguous_rows,
        )
        summary["siglario_ambiguous_raw.csv"]["count"] = len(ambiguous_rows)
    else:
        LOG.warning("Siglario PDF not found: %s", siglario_path)

    # CID-10
    cid10_path = RAW_PDF_DIR / "cid10_problemas.pdf"
    if cid10_path.exists():
        LOG.info("Extracting CID-10 diagnostics")
        cid10_rows = extract_code_name_pdf(cid10_path, CID10_CODE_RE, "cid10", warnings)
        cid10_rows = dedupe_rows(
            [
                {
                    "raw_code": code,
                    "raw_name": name,
                    "source": cid10_path.name,
                    "version": "cid10_br_2008",
                }
                for code, name in cid10_rows
            ],
            ["raw_code", "raw_name"],
        )
        write_csv(
            STAGING_DIR / "cid10_raw.csv",
            ["raw_code", "raw_name", "source", "version"],
            cid10_rows,
        )
        summary["cid10_raw.csv"]["count"] = len(cid10_rows)
    else:
        LOG.warning("CID-10 PDF not found: %s", cid10_path)

    # TUSS Procedures
    tuss_proc_path = RAW_PDF_DIR / "TUSS_22_PROCEDIMENTOSpdf.pdf"
    if tuss_proc_path.exists():
        LOG.info("Extracting TUSS procedures")
        tuss_proc_rows = extract_code_name_pdf(tuss_proc_path, TUSS_CODE_RE, "tuss_proc", warnings)
        tuss_proc_rows = dedupe_rows(
            [
                {
                    "raw_code": code,
                    "raw_term": name,
                    "raw_description": "",
                    "source": tuss_proc_path.name,
                    "version": "tuss_22",
                }
                for code, name in tuss_proc_rows
            ],
            ["raw_code", "raw_term"],
        )
        write_csv(
            STAGING_DIR / "tuss_proc_raw.csv",
            ["raw_code", "raw_term", "raw_description", "source", "version"],
            tuss_proc_rows,
        )
        summary["tuss_proc_raw.csv"]["count"] = len(tuss_proc_rows)
    else:
        LOG.warning("TUSS procedures PDF not found: %s", tuss_proc_path)

    # TUSS Medications
    tuss_drugs_path = RAW_PDF_DIR / "TUSS 20 - Medicamentos - VERSÃO 202511.pdf"
    if tuss_drugs_path.exists():
        LOG.info("Extracting TUSS medications")
        tuss_drugs_rows = extract_code_name_pdf(tuss_drugs_path, TUSS_CODE_RE, "tuss_drugs", warnings)
        tuss_drugs_rows = dedupe_rows(
            [
                {
                    "raw_code": code,
                    "raw_name": name,
                    "raw_description": "",
                    "source": tuss_drugs_path.name,
                    "version": "tuss_20_202511",
                }
                for code, name in tuss_drugs_rows
            ],
            ["raw_code", "raw_name"],
        )
        write_csv(
            STAGING_DIR / "tuss_drugs_raw.csv",
            ["raw_code", "raw_name", "raw_description", "source", "version"],
            tuss_drugs_rows,
        )
        summary["tuss_drugs_raw.csv"]["count"] = len(tuss_drugs_rows)
    else:
        LOG.warning("TUSS medications PDF not found: %s", tuss_drugs_path)

    # Laboratory tests
    labs_path = RAW_PDF_DIR / "Tabela_laboratorios.pdf"
    if labs_path.exists():
        LOG.info("Extracting laboratory tests")
        labs_rows = extract_labs(labs_path, warnings)
        labs_rows = dedupe_rows(
            [
                {
                    "generated_id": f"LAB_{idx:06d}",
                    "raw_exam_name": name,
                    "raw_unit": unit,
                    "raw_method": method,
                    "source": labs_path.name,
                    "version": "labs_v1",
                }
                for idx, (name, unit, method) in enumerate(labs_rows, start=1)
            ],
            ["raw_exam_name", "raw_unit", "raw_method"],
        )
        write_csv(
            STAGING_DIR / "labs_raw.csv",
            ["generated_id", "raw_exam_name", "raw_unit", "raw_method", "source", "version"],
            labs_rows,
        )
        summary["labs_raw.csv"]["count"] = len(labs_rows)
    else:
        LOG.warning("Laboratory tests PDF not found: %s", labs_path)

    # Other PDFs (if present)
    extra_map = {
        "lista_ampla_prontuário.pdf": "lista_ampla_prontuario_raw.csv",
        "siglario_institucional.pdf": "siglario_institucional_raw.csv",
    }
    for pdf_name, output_name in extra_map.items():
        extra_path = RAW_PDF_DIR / pdf_name
        if not extra_path.exists():
            LOG.warning("Extra PDF not found: %s", extra_path)
            continue
        LOG.info("Extracting generic terms from %s", pdf_name)
        terms = extract_generic_terms(extra_path, warnings, pdf_name)
        rows = dedupe_rows(
            [
                {
                    "raw_term": term,
                    "source": pdf_name,
                    "version": "v1",
                }
                for term in terms
            ],
            ["raw_term"],
        )
        write_csv(
            STAGING_DIR / output_name,
            ["raw_term", "source", "version"],
            rows,
        )
        summary[output_name]["count"] = len(rows)

    # Summaries
    total_count = sum(item.get("count", 0) for item in summary.values())
    summary_report = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "staging_dir": str(STAGING_DIR),
        "total_concepts": total_count,
        "files": summary,
        "warnings": warnings[:200],
    }
    summary_path = QA_DIR / "summary_report.json"
    with summary_path.open("w", encoding="utf-8") as handle:
        json.dump(summary_report, handle, ensure_ascii=False, indent=2)

    LOG.info("Extraction complete. Total concepts: %s", total_count)
    LOG.info("Summary report written to %s", summary_path)


if __name__ == "__main__":
    main()
