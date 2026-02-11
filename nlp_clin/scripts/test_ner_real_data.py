"""
Test NER system on real clinical data from pepv1.json
"""
import json
from pathlib import Path
from ner_canonical_loader import CanonicalLexiconLoader
from collections import Counter, defaultdict
import sys

def load_pepv1_data(file_path: str):
    """Load real clinical data from pepv1.json."""
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data

def extract_text_segments(pepv1_data):
    """
    Extract all text segments from pepv1.json.
    
    Returns list of dicts with:
    - segment_id: unique identifier
    - text: the clinical text
    - section: which section it came from
    """
    segments = []
    
    # pepv1.json is a list of clinical case records
    if isinstance(pepv1_data, list):
        for record in pepv1_data:
            segments.append({
                'segment_id': f"case_{record['case_id']}",
                'text': record['raw_text'],
                'section': record.get('group', 'prontuario'),
                'case_id': record['case_id']
            })
    
    return segments

def analyze_ner_results(results: list):
    """
    Analyze NER results and generate quality metrics.
    """
    total_entities = sum(len(r['entities']) for r in results)
    
    if total_entities == 0:
        return {
            'total_segments': len(results),
            'total_entities': 0,
            'avg_entities_per_segment': 0,
            'by_entity_type': {},
            'by_vocabulary': {},
            'avg_confidence': {},
            'ambiguous_entities': 0,
            'ambiguous_rate': 0
        }
    
    # Count by entity type
    entity_type_counts = Counter()
    vocabulary_counts = Counter()
    confidence_dist = defaultdict(list)
    ambiguous_count = 0
    
    for result in results:
        for entity in result['entities']:
            entity_type_counts[entity['entity_type']] += 1
            vocabulary_counts[entity['vocabulary']] += 1
            confidence_dist[entity['entity_type']].append(entity['confidence'])
            
            if entity['match_policy'] == 'context_required':
                ambiguous_count += 1
    
    # Calculate average confidence by entity type
    avg_confidence = {}
    for entity_type, confidences in confidence_dist.items():
        avg_confidence[entity_type] = sum(confidences) / len(confidences)
    
    return {
        'total_segments': len(results),
        'total_entities': total_entities,
        'avg_entities_per_segment': total_entities / len(results) if results else 0,
        'by_entity_type': dict(entity_type_counts),
        'by_vocabulary': dict(vocabulary_counts),
        'avg_confidence': avg_confidence,
        'ambiguous_entities': ambiguous_count,
        'ambiguous_rate': ambiguous_count / total_entities if total_entities else 0
    }

def find_potential_errors(results: list, min_frequency: int = 5):
    """
    Find potential false positives by frequency analysis.
    
    Returns entities that appear very frequently (might be false positives).
    """
    entity_freq = Counter()
    entity_examples = defaultdict(list)
    
    for result in results:
        for entity in result['entities']:
            key = (entity['text'], entity['entity_type'])
            entity_freq[key] += 1
            
            # Store first 3 examples
            if len(entity_examples[key]) < 3:
                entity_examples[key].append({
                    'segment_id': result['segment_id'],
                    'context': result['text'][max(0, entity['start']-30):entity['end']+30]
                })
    
    # Find high-frequency entities
    frequent = [(text, etype, count) 
                for (text, etype), count in entity_freq.most_common(50)
                if count >= min_frequency]
    
    return [{
        'text': text,
        'entity_type': etype,
        'frequency': count,
        'examples': entity_examples[(text, etype)]
    } for text, etype, count in frequent]

def show_sample_results(results: list, num_samples: int = 3):
    """Show detailed results for a few samples."""
    print("\n" + "="*60)
    print("SAMPLE ENTITY DETECTIONS")
    print("="*60)
    
    for result in results[:num_samples]:
        print(f"\n[SAMPLE] {result['segment_id']}")
        print(f"Text preview: {result['text'][:200]}...")
        print(f"Entities found: {len(result['entities'])}")
        
        if result['entities']:
            # Group by entity type
            by_type = defaultdict(list)
            for entity in result['entities']:
                by_type[entity['entity_type']].append(entity)
            
            for etype, entities in sorted(by_type.items()):
                print(f"\n  {etype} ({len(entities)}):")
                for entity in entities[:5]:  # Show first 5 per type
                    print(f"    - '{entity['text']}' -> {entity['concept_name'][:60]}")
                    print(f"      [{entity['vocabulary']}:{entity['concept_id']}, "
                          f"{entity['entry_type']}, conf={entity['confidence']:.2f}, "
                          f"policy={entity['match_policy']}]")

def main():
    print("="*60)
    print("TESTING NER ON REAL CLINICAL DATA (pepv1.json)")
    print("="*60)
    
    # Load NER system
    print("\n[LOADING] Loading NER system...")
    loader = CanonicalLexiconLoader(canonical_version="v1_1")
    loader.load()
    
    # Load real data
    pepv1_path = Path(__file__).parent.parent / "data" / "raw" / "pepv1.json"
    print(f"\n[LOADING] Loading data from: {pepv1_path}")
    
    if not pepv1_path.exists():
        print(f"[ERROR] File not found: {pepv1_path}")
        sys.exit(1)
    
    pepv1_data = load_pepv1_data(pepv1_path)
    segments = extract_text_segments(pepv1_data)
    
    print(f"[OK] Loaded {len(segments)} text segments")
    
    # Run NER on all segments
    print("\n[LOADING] Running NER on all segments...")
    results = []
    
    for i, segment in enumerate(segments, 1):
        if i % 20 == 0:
            print(f"  Processed {i}/{len(segments)} segments...")
        
        entities = loader.match_text(segment['text'])
        results.append({
            'segment_id': segment['segment_id'],
            'text': segment['text'],
            'section': segment['section'],
            'case_id': segment['case_id'],
            'entities': entities
        })
    
    print(f"[OK] Completed NER on {len(results)} segments")
    
    # Analyze results
    print("\n" + "="*60)
    print("ANALYSIS RESULTS")
    print("="*60)
    
    analysis = analyze_ner_results(results)
    
    print(f"\n[STATS] Overall Statistics:")
    print(f"  Total segments: {analysis['total_segments']}")
    print(f"  Total entities detected: {analysis['total_entities']}")
    print(f"  Average per segment: {analysis['avg_entities_per_segment']:.1f}")
    
    if analysis['by_entity_type']:
        print(f"\n[STATS] By Entity Type:")
        for etype, count in sorted(analysis['by_entity_type'].items(), key=lambda x: -x[1]):
            avg_conf = analysis['avg_confidence'].get(etype, 0)
            pct = (count / analysis['total_entities']) * 100
            print(f"  {etype:12s}: {count:5d} ({pct:5.1f}%) - avg conf: {avg_conf:.2f}")
    
    if analysis['by_vocabulary']:
        print(f"\n[STATS] By Vocabulary:")
        for vocab, count in sorted(analysis['by_vocabulary'].items(), key=lambda x: -x[1]):
            pct = (count / analysis['total_entities']) * 100
            print(f"  {vocab:12s}: {count:5d} ({pct:5.1f}%)")
    
    print(f"\n[WARNING] Ambiguous entities: {analysis['ambiguous_entities']} "
          f"({analysis['ambiguous_rate']*100:.1f}%)")
    
    # Show sample results
    show_sample_results(results, num_samples=3)
    
    # Find potential errors
    print("\n" + "="*60)
    print("POTENTIAL FALSE POSITIVES (High Frequency)")
    print("="*60)
    
    potential_errors = find_potential_errors(results, min_frequency=5)
    
    if potential_errors:
        print(f"\n[ANALYSIS] Found {len(potential_errors)} high-frequency entities (may indicate false positives):")
        for error in potential_errors[:20]:  # Show top 20
            print(f"\n  '{error['text']}' ({error['entity_type']}) - {error['frequency']} occurrences")
            if error['examples']:
                context = error['examples'][0]['context']
                # Clean up context for display
                context = context.replace('\n', ' ').strip()
                print(f"    Example: ...{context}...")
    else:
        print("\n[OK] No high-frequency entities detected (good!)")
    
    # Save detailed results
    output_dir = Path(__file__).parent.parent / "data"
    output_file = output_dir / "ner_real_data_results.json"
    
    print(f"\n[SAVING] Saving detailed results...")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            'analysis': analysis,
            'potential_errors': potential_errors,
            'detailed_results': results[:10]  # Save first 10 for inspection
        }, f, ensure_ascii=False, indent=2)
    
    print(f"[OK] Detailed results saved to: {output_file}")
    
    print("\n" + "="*60)
    print("TEST COMPLETE")
    print("="*60)

if __name__ == "__main__":
    main()
