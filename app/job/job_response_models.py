from pydantic import BaseModel
from enum import Enum


class SourceEnvironment(Enum):
    DEVELOPMENT = "DEVELOPMENT"
    PRODUCTION = "PRODUCTION"


class DestinationEnvironment(Enum):
    DEVELOPMENT = "DEVELOPMENT"
    PRODUCTION = "PRODUCTION"
    STAGING = "STAGING"
    LOCAL = "LOCAL"


class JobStatusResponse(BaseModel):
    job_id: str
    text_id: str
    total_segments: int
    completed_segments: int
    status: str


class Span(BaseModel):
    start: int
    end: int


class Segments(BaseModel):
    segment_id: str
    span: Span


class SegmentsRelationRequest(BaseModel):
    text_id: str
    segments: list[Segments]


class MappingSegment(BaseModel):
    segment_id: str
    span: Span


class Mapping(BaseModel):
    text_id: str
    segments: list[MappingSegment]


class SegmentsRelation(BaseModel):
    segment_id: str
    mappings: list[Mapping]


class AllTextSegmentRelationMapping(BaseModel):
    text_id: str
    segments: list[SegmentsRelation]


class SegmentWithSpan(BaseModel):
    segment_id: str
    span: Span


class SegmentationResponse(BaseModel):
    text_id: str
    segments: list[SegmentWithSpan]


class TextIdJobResponse(BaseModel):
    text_id: str
    root_job_id: str | None
    status: str  # "QUEUED" or "SKIPPED_NO_ALIGNMENT"


class PaginatedSegmentRelationResponse(BaseModel):
    text_id: str
    segments: list[SegmentsRelation]
    skip: int
    limit: int
    total: int


class GenerateSegmentsRelationRequest(BaseModel):
    text_ids: list[str]
    source: SourceEnvironment
    destination: DestinationEnvironment
