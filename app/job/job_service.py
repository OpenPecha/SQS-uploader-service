from fastapi import HTTPException
import logging
from app.neo4j_database import Neo4JDatabase
import math
from uuid import uuid4
from app.job.job_respository import (
    get_root_job_by_job_id_repository,
    get_root_job_by_text_id_repository,
    get_total_segment_mapping_count_by_job_id_repository,
    get_segment_mapping_by_job_id_repository,
    create_root_job_repository
)
from app.job.job_response_models import (
    AllTextSegmentRelationMapping,
    SegmentsRelation,
    Mapping,
    PaginatedSegmentRelationResponse,
    TextIdJobResponse,
    SegmentationResponse,
    SegmentWithSpan,
    Span,
    JobStatusResponse,
    GenerateSegmentsRelationRequest
)
from app.job.job_sqs_service import (
    send_segment_batches_to_sqs_service
)

logger = logging.getLogger(__name__)

BATCH_SIZE = 500


def get_job_status_service(job_id: str) -> JobStatusResponse:
    """
    Get job status by job id or text id
    """
    job = get_root_job_by_job_id_repository(job_id)

    return JobStatusResponse(
        job_id=job.job_id,
        text_id=job.text_id,
        total_segments=job.total_segments,
        completed_segments=job.completed_segments,
        status=job.status
    )


def get_all_segments_relation_by_text_id_service(
    text_id: str,
    skip: int = 0,
    limit: int = 100
) -> PaginatedSegmentRelationResponse:
    """
    Get all segments relation by text id
    """

    # Cap limit at 100
    skip, limit = _sanitize_skip_and_limit(skip=skip, limit=limit)

    root_job = get_root_job_by_text_id_repository(text_id)

    if root_job.completed_segments < root_job.total_segments:
        raise HTTPException(
            status_code=400,
            detail="Job not completed"
        )

    # Get total count
    total_count = get_total_segment_mapping_count_by_job_id_repository(
        job_id=root_job.job_id
    )

    # Get paginated results
    paginated_relations = get_segment_mapping_by_job_id_repository(
        job_id=str(root_job.job_id),
        skip=skip,
        limit=limit
    )

    segments = _format_all_text_segment_relation_mapping(
        text_id=text_id,
        all_text_segment_relations=paginated_relations
    )

    return PaginatedSegmentRelationResponse(
        text_id=text_id,
        segments=segments,
        skip=skip,
        limit=limit,
        total=total_count
    )


def generate_all_segments_relation_by_text_ids_service(
    request: GenerateSegmentsRelationRequest
):
    """
    Get all segments relation by text ids
    """
    text_ids = request.text_ids
    if text_ids is None:
        text_ids = []

    try:

        db = Neo4JDatabase(
            source=request.source.value
        )

        # Batch check alignment annotations for all text_ids in a single query
        logger.info(
            "Checking alignment annotations for %d text_ids",
            len(text_ids)
        )
        alignment_map = db.get_text_ids_with_alignment(text_ids=text_ids)

        response_list: list[TextIdJobResponse] = []

        for text_id in text_ids:
            has_alignment = alignment_map.get(text_id, False)

            if not has_alignment:
                # Skip text_ids without alignment annotation
                logger.info(
                    "Text ID %s has no alignment annotation, skipping",
                    text_id
                )
                response_list.append(TextIdJobResponse(
                    text_id=text_id,
                    root_job_id=None,
                    status="SKIPPED_NO_ALIGNMENT"
                ))
                continue

            # Get all segments for this text_id
            all_segments = _get_all_segmentation(
                db=db,
                text_id=text_id
            )

            segments = [{"segment_id": seg.segment_id, "span": seg.span} for seg in all_segments.segments]

            total_segments = len(segments)

            # Create root job
            job_id = _create_root_job(
                total_segments=total_segments,
                text_id=text_id
            )

            # Send batched segment messages to SQS
            send_segment_batches_to_sqs_service(
                root_job_id=job_id,
                text_id=text_id,
                segments=segments,
                source_environment=request.source.value,
                destination_environment=request.destination.value
            )

            logger.info(
                "Created job %s for text_id %s with %d batches",
                job_id, text_id, total_segments
            )
            response_list.append(TextIdJobResponse(
                text_id=text_id,
                root_job_id=job_id,
                status="QUEUED"
            ))

        return response_list
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Error in get_all_segments_relation_by_text_id: %s",
            str(e)
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process text_ids, Error: {str(e)}"
        ) from e


def _create_root_job(total_segments: int, text_id: str) -> str:
    """
    Create a root job
    """
    job_id = create_root_job_repository(
        total_segments=total_segments,
        text_id=text_id
    )
    return job_id


def _format_all_text_segment_relation_mapping(
    text_id: str,
    all_text_segment_relations
):
    """
    Format all text segment relation mapping
    """
    response = AllTextSegmentRelationMapping(
        text_id=text_id,
        segments=[]
    )
    for task in all_text_segment_relations:
        task_dict = _get_task_dict(task=task)
        logger.info("Starting with formatting task: %s", task_dict)
        
        segment = _get_segment_formatted(task_dict=task_dict)
        logger.info("Segment: %s", segment)

        response.segments.append(segment)
    logger.info("Response: %s", response)
    return response


def _get_segment_formatted(task_dict: dict) -> SegmentsRelation:
    """
    Get the segment formatted
    """
    segment = SegmentsRelation(
            segment_id=task_dict["segment_id"],
            mappings=[]
        )
    for mapping in task_dict["result_json"]:
        mapping_dict = Mapping(
            text_id=mapping["manifestation_id"],
            segments=mapping["segments"]
        )
        segment.mappings.append(mapping_dict)
    return segment


def _get_task_dict(task) -> dict:
    """
    Get the task dictionary
    """
    task_dict = {
            "task_id": str(task.task_id),
            "root_job_id": str(task.root_job_id),
            "text_id": task.text_id,
            "segment_id": task.segment_id,
            "status": task.status,
            "result_json": task.result_json,
            "error_message": task.error_message,
            "created_at": (
                task.created_at.isoformat() if task.created_at else None
            ),
            "updated_at": (
                task.updated_at.isoformat() if task.updated_at else None
            )
        }
    return task_dict


def _get_all_segmentation(
    db: Neo4JDatabase,
    text_id: str
) -> SegmentationResponse:
    """Helper function to get all segments from segmentation annotation"""
    try:
        segments_data = db.get_segments_by_manifestation(text_id)

        if not segments_data:
            raise HTTPException(
                status_code=404,
                detail="Segmentation annotation not available"
            )
        segments = [
            SegmentWithSpan(
                segment_id=seg["segment_id"],
                span=Span(start=seg["span_start"], end=seg["span_end"])
            )
            for seg in segments_data
        ]

        return SegmentationResponse(
            text_id=text_id,
            segments=segments
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error getting segments: %s", str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Database error: {str(e)}"
        ) from e


def _sanitize_skip_and_limit(skip: int, limit: int) -> tuple[int, int]:
    """
    Sanitize the skip and limit
    """
    if skip < 0:
        skip = 0
    if limit > 100:
        limit = 100
    return skip, limit
