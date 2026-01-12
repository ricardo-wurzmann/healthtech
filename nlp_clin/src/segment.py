from __future__ import annotations
from dataclasses import dataclass
from typing import List, Tuple
import spacy

_nlp = spacy.load("pt_core_news_sm", disable=["tagger", "parser", "ner", "lemmatizer"])

# Ensure we have a component that sets sentence boundaries, since we've disabled the parser.
if "sentencizer" not in _nlp.pipe_names:
    _nlp.add_pipe("sentencizer")


@dataclass
class Sentence:
    text: str
    start: int
    end: int


def split_sentences(text: str) -> List[Sentence]:
    doc = _nlp(text)
    out: List[Sentence] = []
    for sent in doc.sents:
        s = sent.text.strip()
        if not s:
            continue
        out.append(Sentence(text=s, start=sent.start_char, end=sent.end_char))
    return out
