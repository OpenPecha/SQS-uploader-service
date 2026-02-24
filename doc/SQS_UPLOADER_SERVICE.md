# SQS Uploader Service — Documentation

---

## Introduction

The **SQS Uploader Service** is the entry point of the pipeline. It is a FastAPI service that receives segment relation processing requests, validates and prepares jobs, fetches eligible segment data from the OpenPecha backend (via Neo4j), stores/updates root job records in PostgreSQL, and publishes batched processing tasks to Amazon SQS.

This service helps decouple request submission from heavy processing by pushing work asynchronously to the queue.

---

## 1. Service overview

### Purpose

The service is the entry point for segment-relation processing. It:

- Accepts requests with a list of text IDs (manifestation IDs) and source/destination environments.
- Validates the request and checks which text IDs have alignment annotations in Neo4j.
- Fetches segment data from Neo4j for eligible text IDs.
- Creates or resets root job records in PostgreSQL.
- Publishes batched segment messages to Amazon SQS for downstream processing.

### Role in the pipeline

The SQS Uploader Service decouples **request submission** from **heavy processing**. Clients submit work via the API; the service enqueues tasks to SQS. Downstream consumers pull messages from the queue and perform the actual segment-relation processing. This allows the API to respond quickly while processing happens asynchronously.

### High-level workflow

```mermaid
flowchart LR
    A[Request] --> B[Pydantic validate]
    B --> C[Neo4j batch alignment]
    C --> D{Eligible text_ids}
    D -->|Per text_id| E[Fetch segments]
    E --> F[Create/update root_job]
    F --> G[Send batches to SQS]
    G --> H[Return QUEUED / SKIPPED]
    D -->|No alignment| H
```

1. **Request** — `POST /job/text-ids` with `text_ids`, `source`, `destination`.
2. **Validate** — Pydantic validates the body; invalid payload returns 422.
3. **Neo4j batch alignment** — Single query checks which `text_ids` have an alignment annotation.
4. **Per eligible text_id** — Fetch all segments from Neo4j, create or update the root job in PostgreSQL, split segments into batches of 500, send each batch as one SQS message.
5. **Response** — One entry per `text_id`: either `QUEUED` (with `root_job_id`) or `SKIPPED_NO_ALIGNMENT`.

---

## 2. API and input handling

### Endpoints

| Method | Path | Description | Response |
|--------|------|-------------|----------|
| `GET` | `/` | Service info | 200, `{ service, version, status }` |
| `GET` | `/health` | Health check | 200, `{ status: "healthy" }` |
| `GET` | `/job/{job_id}/status` | Job status by job ID | 200, `JobStatusResponse` |
| `GET` | `/job/{text_id}/segments-relations` | Paginated segment relations by text ID | 200, `PaginatedSegmentRelationResponse` |
| `POST` | `/job/text-ids` | Create segment-relation jobs for given text IDs | 201, `list[TextIdJobResponse]` |

- **GET /job/{text_id}/segments-relations** supports query parameters: `skip` (default 0), `limit` (default 100, max 100). The job for that `text_id` must exist and be completed (`completed_segments >= total_segments`); otherwise the API returns 400 or 500 depending on state.

### Request schema (POST /job/text-ids)

The body is **GenerateSegmentsRelationRequest**:

| Field | Type | Description |
|-------|------|-------------|
| `text_ids` | `list[str]` | List of text IDs (manifestation IDs in Neo4j). |
| `source` | `SourceEnvironment` | Neo4j environment to read from. |
| `destination` | `DestinationEnvironment` | Environment passed to downstream via SQS. |

**Enums:**

- **SourceEnvironment:** `DEVELOPMENT`, `PRODUCTION`
- **DestinationEnvironment:** `DEVELOPMENT`, `PRODUCTION`, `STAGING`

### text_ids, source, and destination

- **text_ids** — Treated as manifestation IDs in the OpenPecha/Neo4j graph. Used to check alignment annotations and to fetch segments (segmentation/pagination annotations). Each ID can result in one root job and multiple SQS batches.
- **source** — Selects which Neo4j instance to use via config: `{SOURCE}_NEO4J_URI`, `{SOURCE}_NEO4J_PASSWORD` (e.g. `DEVELOPMENT_NEO4J_URI`, `PRODUCTION_NEO4J_URI`).
- **destination** — Not used for Neo4j; included in every SQS message body so downstream processors know the target environment.

---

## 3. Data preparation

### Neo4j alignment checks

- Alignment is checked in batch for all requested `text_ids` in a single Neo4j query.
- Query (conceptually): for each `text_id`, match the `Manifestation` node and optionally an `Annotation` of type `alignment`; return whether each has alignment.
- Result is a map `text_id → has_alignment` (boolean). Only `text_id`s with alignment are processed; others are returned as `SKIPPED_NO_ALIGNMENT`.

### Segment fetching

- For each `text_id` with alignment, the service fetches **all** segments for that manifestation in one call.
- Segments come from annotations of type `segmentation` or `pagination`, ordered by `span_start`.
- Returned fields: `segment_id`, `span_start`, `span_end`. These are converted to the internal shape `segment_id` + `span: { start, end }` for the job and SQS payload.

### Pagination and batching

- **Neo4j:** There is no pagination at the Neo4j layer; all segments for a manifestation are fetched once.
- **SQS batching:** Segments are split into fixed-size chunks of **500** (configurable in code as `BATCH_SIZE` / `batch_size`). One SQS message is sent per chunk.
- **GET segments-relations:** Pagination is applied when reading results from PostgreSQL (`segment_mapping` table): `skip` and `limit` (max 100) are used for the response.

---

## 4. Root job management

### Table: root_jobs

Root jobs are stored in PostgreSQL in the **root_jobs** table:

| Column | Type | Description |
|--------|------|-------------|
| `job_id` | UUID (PK) | Generated on create. |
| `text_id` | Text | Manifestation ID. |
| `total_segments` | Integer | Total segments for this job. |
| `completed_segments` | Integer | Number of segments completed (updated by downstream). |
| `status` | String | One of: `QUEUED`, `IN_PROGRESS`, `COMPLETED`, `FAILED`. |
| `created_at` | DateTime | Creation time (UTC). |
| `updated_at` | DateTime | Last update time (UTC). |

### Create / reset behavior

- **Function:** `create_root_job_repository(total_segments, text_id)` (repository layer).
- **Logic:**
  - If a root job already exists for the given `text_id` (latest by `created_at`), it **updates** that row: sets `total_segments`, `completed_segments = 0`, `status = "QUEUED"`, and `updated_at`; returns the existing `job_id`.
  - Otherwise it **inserts** a new row with the same fields and returns the new `job_id`.
- **When called:** From the job service after segment count is known for an eligible `text_id`, and **before** sending any batches to SQS. So each submission for a given `text_id` either creates a new root job or resets the existing one and re-queues work.

---

## 5. SQS publishing

### Queue and client

- **Queue:** The queue is identified by URL only. The URL is read from the environment variable **SQS_QUEUE_URL** (no queue name in code).
- **Client:** boto3 SQS client, created with:
  - `region_name` from **AWS_REGION**
  - **AWS_ACCESS_KEY_ID** and **AWS_SECRET_ACCESS_KEY** from config (env).

### Message publishing flow

1. For each `text_id` with alignment, after creating/updating the root job:
2. Segments are split into batches of 500.
3. For each batch, the service builds a JSON body with `_prepare_message_body` and calls `sqs_client.send_message(QueueUrl=..., MessageBody=json.dumps(...))`.
4. One `send_message` call per batch (no `send_message_batch`).
5. Logs: info per batch (e.g. "Sent batch 1/3 for text_id ...") and a final info (e.g. "Successfully sent N batches to SQS for text_id ...").

### Batching strategy

- **Batch size:** 500 segments per message (default; can be overridden where `send_segment_batches_to_sqs_service` is called).
- **Number of batches:** `total_batches = ceil(len(segments) / batch_size)`.
- **Order:** Batches are sent in order (batch index 0, 1, …); `batch_number` in the payload is 1-based for readability.

---

## 6. SQS message payload

### Message body schema

Each SQS message body is a JSON object with the following fields:

| Field | Type | Description |
|-------|------|-------------|
| `root_job_id` | string | UUID of the root job. |
| `text_id` | string | Manifestation ID. |
| `batch_number` | integer | 1-based index of this batch (1, 2, 3, …). |
| `total_segments` | integer | Total number of segments for this text/job. |
| `segments` | array | Segment objects in this batch (up to 500). |
| `source_environment` | string | Source environment (e.g. `"DEVELOPMENT"`, `"PRODUCTION"`). |
| `destination_environment` | string | Destination environment (e.g. `"DEVELOPMENT"`, `"PRODUCTION"`, `"STAGING"`). |

### Segment object

Each element of `segments` has:

| Field | Type | Description |
|-------|------|-------------|
| `segment_id` | string | Segment identifier. |
| `span` | object | `{ "start": number, "end": number }` (character offsets). |

### Sample JSON

```json
{
  "root_job_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "text_id": "I1234567890",
  "batch_number": 1,
  "total_segments": 1200,
  "segments": [
    {
      "segment_id": "seg-001",
      "span": { "start": 0, "end": 150 }
    },
    {
      "segment_id": "seg-002",
      "span": { "start": 150, "end": 320 }
    }
  ],
  "source_environment": "DEVELOPMENT",
  "destination_environment": "PRODUCTION"
}
```

---

## 7. Error handling and logging

### Validation

- **POST /job/text-ids:** The request body is validated by Pydantic. Invalid or missing fields (e.g. wrong types, missing `source`/`destination`) result in **422 Unprocessable Entity** with validation error details.

### Neo4j and segment fetching

- **No segmentation data:** If there are no segments for a manifestation (e.g. missing or empty segmentation annotation), the service raises **404** with detail `"Segmentation annotation not available"`.
- **Other Neo4j/DB errors:** Exceptions during segment fetch or alignment check are logged and re-raised as **500** with a message (e.g. "Database error: ..."). `HTTPException` is re-raised as-is.

### PostgreSQL

- **Job not found by job_id:** `GET /job/{job_id}/status` (and any logic that fetches by `job_id`) returns **404** with detail `"Job or text id not found"` when no root job exists.
- **Repository read errors:** Other database read errors in the repository (e.g. get root job by text_id) are logged and result in **500** with detail like "Failed to get root job by text id, Database read error".
- **Create/update root job failure:** If `create_root_job_repository` fails, the service returns **500** with detail "Failed to get/create root job, Database error".

### SQS

- On any exception during `send_message` (e.g. network, permissions, invalid URL), the service:
  - Logs an error with batch index and `text_id`.
  - Raises **500** with detail like "Failed to send SQS message for batch N: ...".

### Job not completed

- **GET /job/{text_id}/segments-relations:** If the root job exists but `completed_segments < total_segments`, the API returns **400** with detail `"Job not completed"`.

### Logging

- **Configuration:** `logging.basicConfig(level=logging.INFO)` is set in the main application entry point. Module-level loggers are used in the job service, job repository, SQS service, and Neo4j database module.
- **Info:** Alignment check count, skipping text_id (no alignment), batch send progress, and successful total batches sent.
- **Error:** Exceptions (Neo4j, Postgres, SQS) are logged with context before raising or re-raising HTTP exceptions.

---

## 8. Configuration and libraries

### Environment variables

The service reads configuration from the environment (e.g. via `.env` and `python-dotenv`). Relevant variables (as used in `app/config.py`) are:

| Variable | Description | Default / note |
|----------|-------------|----------------|
| `NEO4J_USER` | Neo4j username | Optional; default not set in config. |
| `DEVELOPMENT_NEO4J_URI` | Neo4j URI for development source. | Required when using source=DEVELOPMENT. |
| `DEVELOPMENT_NEO4J_PASSWORD` | Neo4j password for development. | Required when using source=DEVELOPMENT. |
| `PRODUCTION_NEO4J_URI` | Neo4j URI for production source. | Required when using source=PRODUCTION. |
| `PRODUCTION_NEO4J_PASSWORD` | Neo4j password for production. | Required when using source=PRODUCTION. |
| `POSTGRES_URL` | PostgreSQL connection string. | Default: `postgresql://admin:pechaAdmin@localhost:5435/pecha`. |
| `AWS_REGION` | AWS region for SQS. | Default: `us-east-1`. |
| `AWS_ACCESS_KEY_ID` | AWS access key. | Required for SQS. |
| `AWS_SECRET_ACCESS_KEY` | AWS secret key. | Required for SQS. |
| `SQS_QUEUE_URL` | Full URL of the SQS queue. | Required for publishing. |

Note: The repository’s `env.example` may mention Celery, Redis, or Render; the SQS Uploader Service itself uses only the variables above (Neo4j, Postgres, AWS/SQS).

### Dependencies

From **requirements.txt** (pinned versions):

- **fastapi** 0.104.1 — Web framework.
- **uvicorn** 0.24.0 (with standard extras) — ASGI server.
- **pydantic** 2.5.0 — Request/response and config validation.
- **sqlalchemy** 2.0.35 — PostgreSQL ORM.
- **alembic** 1.12.0 — Database migrations.
- **psycopg2-binary** 2.9.9 — PostgreSQL driver.
- **neo4j** 5.28.2 — Neo4j Python driver.
- **python-dotenv** 1.0.0 — Load `.env` into environment.
- **boto3** 1.40.74 — AWS SDK (SQS).

### Frameworks and libraries in use

- **FastAPI** — HTTP API, routing, dependency injection, OpenAPI.
- **SQLAlchemy** — PostgreSQL access and `root_jobs` / `segment_mapping` models.
- **Neo4j Python driver** — Neo4j connectivity and Cypher execution.
- **boto3** — SQS client for publishing messages.
- **Pydantic** — Request/response models and serialization.
- **Alembic** — Schema migrations for the application database.

---