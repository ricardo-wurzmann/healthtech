"""
Debug tracer for tracking entities through the pipeline.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional
from enum import Enum


class MatchStrategy(Enum):
    REGEX = "regex"
    EXACT = "exact"
    TOKEN = "token"
    FUZZY = "fuzzy"


class EntityStatus(Enum):
    CANDIDATE = "candidate"
    KEPT = "kept"
    FILTERED = "filtered"
    OVERLAP_REMOVED = "overlap_removed"
    DUPLICATE = "duplicate"


@dataclass
class EntityTrace:
    """Trace record for a single entity candidate."""
    span: str
    start: int
    end: int
    entity_type: str
    source_lexicon: Optional[str] = None
    match_strategy: Optional[str] = None
    raw_score: float = 0.0
    status: str = EntityStatus.CANDIDATE.value
    discard_reason: Optional[str] = None
    assertion: Optional[str] = None
    evidence: Optional[str] = None
    
    def to_dict(self) -> dict:
        return asdict(self)


class PipelineTracer:
    """Tracks entities through the pipeline."""
    
    def __init__(self):
        self.traces: List[EntityTrace] = []
        self.stage_counts: Dict[str, int] = {}
    
    def add_candidate(self, span: str, start: int, end: int, entity_type: str,
                     source_lexicon: Optional[str] = None,
                     match_strategy: Optional[str] = None,
                     raw_score: float = 0.0,
                     evidence: Optional[str] = None) -> EntityTrace:
        """Add a candidate entity."""
        trace = EntityTrace(
            span=span,
            start=start,
            end=end,
            entity_type=entity_type,
            source_lexicon=source_lexicon,
            match_strategy=match_strategy,
            raw_score=raw_score,
            status=EntityStatus.CANDIDATE.value,
            evidence=evidence
        )
        self.traces.append(trace)
        return trace
    
    def mark_kept(self, trace: EntityTrace, assertion: Optional[str] = None):
        """Mark an entity as kept in final output."""
        trace.status = EntityStatus.KEPT.value
        trace.assertion = assertion
    
    def mark_filtered(self, trace: EntityTrace, reason: str):
        """Mark an entity as filtered out."""
        trace.status = EntityStatus.FILTERED.value
        trace.discard_reason = reason
    
    def mark_overlap_removed(self, trace: EntityTrace, reason: str):
        """Mark an entity as removed due to overlap."""
        trace.status = EntityStatus.OVERLAP_REMOVED.value
        trace.discard_reason = reason
    
    def mark_duplicate(self, trace: EntityTrace):
        """Mark an entity as duplicate."""
        trace.status = EntityStatus.DUPLICATE.value
        trace.discard_reason = "exact duplicate (same start/end/type)"
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about traced entities."""
        stats = {
            "total_candidates": len(self.traces),
            "by_status": {},
            "by_entity_type": {},
            "by_source_lexicon": {},
            "by_match_strategy": {},
            "filter_reasons": {},
            "overlap_reasons": {}
        }
        
        for trace in self.traces:
            # By status
            stats["by_status"][trace.status] = stats["by_status"].get(trace.status, 0) + 1
            
            # By entity type
            stats["by_entity_type"][trace.entity_type] = stats["by_entity_type"].get(trace.entity_type, 0) + 1
            
            # By source lexicon
            source = trace.source_lexicon or "unknown"
            stats["by_source_lexicon"][source] = stats["by_source_lexicon"].get(source, 0) + 1
            
            # By match strategy
            strategy = trace.match_strategy or "unknown"
            stats["by_match_strategy"][strategy] = stats["by_match_strategy"].get(strategy, 0) + 1
            
            # Filter reasons
            if trace.status == EntityStatus.FILTERED.value and trace.discard_reason:
                stats["filter_reasons"][trace.discard_reason] = stats["filter_reasons"].get(trace.discard_reason, 0) + 1
            
            # Overlap reasons
            if trace.status == EntityStatus.OVERLAP_REMOVED.value and trace.discard_reason:
                stats["overlap_reasons"][trace.discard_reason] = stats["overlap_reasons"].get(trace.discard_reason, 0) + 1
        
        return stats
    
    def to_dict_list(self) -> List[dict]:
        """Convert all traces to list of dicts."""
        return [trace.to_dict() for trace in self.traces]
    
    def clear(self):
        """Clear all traces."""
        self.traces = []
        self.stage_counts = {}


# Global tracer instance
_global_tracer: Optional[PipelineTracer] = None


def get_tracer() -> PipelineTracer:
    """Get the global tracer instance."""
    global _global_tracer
    if _global_tracer is None:
        _global_tracer = PipelineTracer()
    return _global_tracer


def reset_tracer():
    """Reset the global tracer."""
    global _global_tracer
    _global_tracer = PipelineTracer()

