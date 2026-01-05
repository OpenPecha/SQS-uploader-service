"""
Importing neccessary libraries for relation endpoints
"""
import logging
from fastapi import APIRouter
from app.job.job_response_models import (
    TextIdJobResponse,
    PaginatedSegmentRelationResponse
)
from app.job.job_service import (
    get_job_status_service,
    get_all_segments_relation_by_text_id_service,
    generate_all_segments_relation_by_text_ids_service
)

job_router = APIRouter(
    prefix="/job",
    tags=["Job"]
)

logger = logging.getLogger(__name__)


@job_router.get("/{job_id}/status")
def get_job_status(job_id: str):
    """
    Get job status by job id
    """
    return get_job_status_service(
        job_id=job_id
    )


@job_router.get("/{text_id}/segments-relations")
def get_all_segments_relation_by_text_id(
    text_id: str,
    skip: int = 0,
    limit: int = 100
) -> PaginatedSegmentRelationResponse:
    """
    Get all segments relation by manifestation id with pagination.

    Args:
        text_id: The manifestation ID
        skip: Number of records to skip (default 0)
        limit: Maximum number of records to return (default 100, max 100)
    """
    return get_all_segments_relation_by_text_id_service(
        text_id=text_id,
        skip=skip,
        limit=limit
    )


@job_router.post("/text-ids")
def generate_all_segments_relation_by_text_ids(
    text_ids: list[str] = None
) -> list[TextIdJobResponse]:
    """
    Process multiple text_ids, check alignment annotations, create root jobs,
    and send batched segment messages to SQS.
    """
    return generate_all_segments_relation_by_text_ids_service(
        text_ids=text_ids
    )
