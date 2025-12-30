from app.db.postgres import SessionLocal
from fastapi import HTTPException
from datetime import datetime, timezone
import logging
from app.db.models import (
    RootJob,
    SegmentMapping
)

logger = logging.getLogger(__name__)


def get_root_job_by_job_id_or_text_id_repository(job_id_or_text_id: str):
    try:
        with SessionLocal() as session:
            job = session.query(RootJob).filter(
                (RootJob.job_id == job_id_or_text_id)
                | (RootJob.manifestation_id == job_id_or_text_id)
            ).first()
            if not job:
                raise HTTPException(
                    status_code=404,
                    detail="Job or text id not found"
                )
            return job
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error in get_job_status: %s", str(e))
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get job status, Database read error: {str(e)}"
        ) from e

def get_total_segment_mapping_count_by_job_id_repository(job_id: str):
    with SessionLocal() as session:
        return session.query(SegmentMapping).filter(
            SegmentMapping.job_id == job_id
        ).count()

def get_segment_mapping_by_job_id_repository(
    job_id: str,
    skip: int = 0,
    limit: int = 100
):
    with SessionLocal() as session:
        return session.query(SegmentMapping).filter(
                SegmentMapping.job_id == job_id
            ).offset(skip).limit(limit).all()

def create_root_job_repository(job_id: str, total_batch: int, manifestation_id: str):
    """Create a root job record in the database."""
    try:
        with SessionLocal() as session:
            session.add(
                RootJob(
                    job_id=job_id,
                    manifestation_id=manifestation_id,
                    total_batch=total_batch,
                    completed_batch=0,
                    status="QUEUED",
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc)
                )
            )
            session.commit()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail="Failed to create root job, Database write error"
        ) from e
