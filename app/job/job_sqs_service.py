import boto3
from fastapi import HTTPException
import logging
import json
import math
from app.config import get

logger = logging.getLogger(__name__)

sqs_client = boto3.client(
    'sqs',
    region_name=get('AWS_REGION'),
    aws_access_key_id=get('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=get('AWS_SECRET_ACCESS_KEY')
)


def send_segment_batches_to_sqs_service(
    job_id: str,
    text_id: str,
    segment_ids: list[str],
    batch_size: int = 500
):
    """
    Send segment batches to SQS. Each message contains up to batch_size
    segment IDs.

    Args:
        job_id: The root job ID
        text_id: The text/manifestation ID
        segment_ids: List of all segment IDs to process
        batch_size: Number of segments per batch (default 500)
    """
    total_batches = math.ceil(len(segment_ids) / batch_size)
    total_sent = 0

    for batch_number in range(total_batches):
        start_idx = batch_number * batch_size
        end_idx = min(start_idx + batch_size, len(segment_ids))
        batch_segment_ids = segment_ids[start_idx:end_idx]

        message_body = _prepare_message_body(
            job_id=job_id,
            text_id=text_id,
            segment_ids=batch_segment_ids,
            batch_number=batch_number,
            total_batches=total_batches
        )

        try:
            sqs_client.send_message(
                QueueUrl=get("SQS_QUEUE_URL"),
                MessageBody=json.dumps(message_body)
            )
            total_sent += 1
            logger.info(
                "Sent batch %d/%d for text_id %s",
                batch_number + 1, total_batches, text_id
            )
        except Exception as e:
            logger.error(
                "Failed to send batch %d for text_id %s: %s",
                batch_number + 1, text_id, str(e)
            )
            raise HTTPException(
                status_code=500,
                detail=f"Failed to send SQS message for batch "
                       f"{batch_number + 1}: {str(e)}"
            ) from e

    logger.info(
        "Successfully sent %d batches to SQS for text_id %s",
        total_sent, text_id
    )


def _prepare_message_body(
    job_id: str,
    text_id: str,
    batch_number: int,
    total_batches: int,
    batch_segment_ids: list[str]
) -> dict:
    """
    Prepare the message body for the SQS message.
    """
    message_body = {
            "job_id": job_id,
            "text_id": text_id,
            "batch_number": batch_number + 1,  # 1-indexed for readability
            "total_batches": total_batches,
            "segment_ids": batch_segment_ids
        }
    return message_body