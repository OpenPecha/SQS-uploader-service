class Queries:
    pass


Queries.annotations = {
    "has_alignment_annotation": """
MATCH (m:Manifestation {id: $manifestation_id})
OPTIONAL MATCH (m)<-[:ANNOTATION_OF]-(a:Annotation)-[:HAS_TYPE]->(:AnnotationType {name: 'alignment'})
RETURN COUNT(a) > 0 as has_alignment
""",
    "batch_has_alignment_annotation": """
UNWIND $text_ids AS text_id
MATCH (m:Manifestation {id: text_id})
OPTIONAL MATCH (m)<-[:ANNOTATION_OF]-(a:Annotation)-[:HAS_TYPE]->(:AnnotationType {name: 'alignment'})
RETURN text_id, COUNT(a) > 0 as has_alignment
""",
}

Queries.segments = {
    "get_segments_by_manifestation": """
MATCH (m:Manifestation {id: $manifestation_id})<-[:ANNOTATION_OF]-(ann:Annotation)-[:HAS_TYPE]->(at:AnnotationType)
WHERE at.name IN ['segmentation', 'pagination']
MATCH (ann)<-[:SEGMENTATION_OF]-(s:Segment)
RETURN s.id as segment_id,
       s.span_start as span_start,
       s.span_end as span_end
ORDER BY s.span_start
"""
}
