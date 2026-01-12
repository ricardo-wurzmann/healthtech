from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import List
from pypdf import PdfReader


@dataclass
class Document:
    doc_id: str
    text: str
    source_path: str


def extract_text_from_pdf(pdf_path: str | Path) -> str:
    pdf_path = Path(pdf_path)
    reader = PdfReader(str(pdf_path))
    pages: List[str] = []
    for i, page in enumerate(reader.pages):
        t = page.extract_text() or ""
        t = t.replace("\x00", " ")
        pages.append(t)
    return "\n".join(pages)


def load_pdf_as_document(pdf_path: str | Path, doc_id: str | None = None) -> Document:
    pdf_path = Path(pdf_path)
    text = extract_text_from_pdf(pdf_path)
    return Document(
        doc_id=doc_id or pdf_path.stem,
        text=text,
        source_path=str(pdf_path),
    )
