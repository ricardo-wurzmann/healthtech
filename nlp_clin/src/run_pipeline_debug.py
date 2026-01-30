from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any, Dict, List

from src.preprocess import normalize_text
from src.segment import split_sentences
from src.baseline_ner import extract_entities_baseline
from src.context import classify_assertion
from src.postprocess.filters import filter_entities, FilterConfig
from src.schema import DocOut, EntityOut


def _entity_key(entity: Dict[str, Any]) -> str:
    return json.dumps(entity, sort_keys=True, ensure_ascii=False)


def _build_filter_log(
    before: List[Dict[str, Any]],
    after: List[Dict[str, Any]],
) -> Dict[str, Any]:
    before_keys = {_entity_key(e) for e in before}
    after_keys = {_entity_key(e) for e in after}
    filtered_keys = before_keys - after_keys
    filtered_out = [e for e in before if _entity_key(e) in filtered_keys]

    return {
        "before_count": len(before),
        "after_count": len(after),
        "filtered_count": len(before) - len(after),
        "filtered_out": filtered_out,
    }


def _build_final_output(text: str, entities_filtered: List[Dict[str, Any]]) -> Dict[str, Any]:
    entities_out = []
    for e_dict in entities_filtered:
        entities_out.append(
            EntityOut(
                span=e_dict.get("span") or e_dict.get("text", ""),
                start=e_dict["start"],
                end=e_dict["end"],
                type=e_dict["type"],
                score=e_dict["score"],
                assertion=e_dict.get("assertion", ""),
                evidence=e_dict.get("evidence", ""),
                links=[],
                icd10=[],
            )
        )

    result = DocOut(
        doc_id="debug_input",
        source="inline",
        text=text,
        entities=entities_out,
        case_id=0,
        group="debug",
    )

    return asdict(result)


def run_pipeline_debug(text: str) -> Dict[str, Any]:
    raw_text = text or ""
    preprocessed_text = normalize_text(raw_text)

    sents = split_sentences(preprocessed_text)
    sentences = [{"text": s.text, "start": s.start, "end": s.end} for s in sents]
    sentence_tuples = [(s.text, s.start, s.end) for s in sents]

    spans = extract_entities_baseline(preprocessed_text, sentence_tuples)

    entities_before = []
    for e in spans:
        sentence_text = preprocessed_text[e.sentence_start : e.sentence_end]
        ent_start_in_sent = e.start - e.sentence_start
        ent_end_in_sent = e.end - e.sentence_start
        assertion = classify_assertion(
            sentence_text,
            ent_start_in_sent,
            ent_end_in_sent,
            e.type,
        )

        entities_before.append(
            {
                "span": e.span,
                "start": e.start,
                "end": e.end,
                "type": e.type,
                "score": float(e.score),
                "assertion": assertion,
                "evidence": e.evidence,
            }
        )

    filter_config = FilterConfig()
    entities_after = filter_entities(entities_before, preprocessed_text, filter_config)
    filter_log = _build_filter_log(entities_before, entities_after)
    final_output = _build_final_output(preprocessed_text, entities_after)

    return {
        "raw_text": raw_text,
        "preprocessed_text": preprocessed_text,
        "sentences": sentences,
        "entities_before_filter": entities_before,
        "entities_after_filter": entities_after,
        "filter_log": filter_log,
        "final_output": final_output,
    }
