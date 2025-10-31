"""
ABOUTME: Pydantic models for data validation and serialization
ABOUTME: Defines schemas for documents, chunks, queries, and API responses
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ChunkType(str, Enum):
    """Types of document chunks"""

    SECTION = "section"
    CLAUSE = "clause"
    PARAGRAPH = "paragraph"
    SUBSECTION = "subsection"


class DocumentStatus(str, Enum):
    """Document status"""

    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


# Database Models (matches SQL schema)


class DocumentDB(BaseModel):
    """Document metadata (database model)"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    filename: str
    doc_hash: str
    file_size_bytes: int
    uploaded_at: datetime
    metadata: Dict[str, Any] = Field(default_factory=dict)
    version: int = 1
    status: DocumentStatus = DocumentStatus.ACTIVE


class ChunkDB(BaseModel):
    """Document chunk with embedding (database model)"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    section_id: str
    parent_id: Optional[uuid.UUID] = None
    content: str
    chunk_type: ChunkType
    position: int
    metadata: Dict[str, Any] = Field(default_factory=dict)
    embedding: Optional[List[float]] = None
    created_at: datetime


class QueryLogDB(BaseModel):
    """Query log entry (database model)"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    query_hash: str
    response_hash: Optional[str] = None
    created_at: datetime
    latency_ms: Optional[int] = None
    tokens_used: Optional[int] = None
    model_version: Optional[str] = None
    citations_count: Optional[int] = None
    confidence_score: Optional[float] = None
    error_message: Optional[str] = None


# API Request/Response Models


class DocumentUpload(BaseModel):
    """Document upload request"""

    filename: str
    content: bytes = Field(..., description="Raw file content")
    user_id: uuid.UUID
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DocumentIndexResponse(BaseModel):
    """Response after indexing a document"""

    document_id: uuid.UUID
    filename: str
    chunks_created: int
    status: str
    message: str


class Citation(BaseModel):
    """Single citation reference"""

    section_id: str
    content: str
    confidence: float = Field(ge=0.0, le=1.0)
    chunk_id: uuid.UUID


class AnalyzeRequest(BaseModel):
    """Document analysis request"""

    file_id: str = Field(..., description="Document UUID")
    query: str = Field(..., min_length=1, max_length=10000)
    top_k: int = Field(default=5, ge=1, le=20, description="Number of chunks to retrieve")

    @field_validator("file_id")
    @classmethod
    def validate_uuid(cls, v: str) -> str:
        """Ensure file_id is valid UUID"""
        try:
            uuid.UUID(v)
        except ValueError:
            raise ValueError("file_id must be a valid UUID")
        return v


class AnalyzeResponse(BaseModel):
    """Document analysis response"""

    answer: str
    citations: List[Citation]
    confidence: float = Field(ge=0.0, le=1.0)
    request_id: str
    unsupported_claims: List[str] = Field(
        default_factory=list, description="Claims without source support"
    )
    metadata: Dict[str, Any] = Field(default_factory=dict)


class VerificationResult(BaseModel):
    """Verification check result"""

    is_supported: bool
    citation_matches: List[str]
    unsupported_statements: List[str]
    confidence: float


# Internal Processing Models


class Section(BaseModel):
    """Hierarchical document section"""

    section_id: str
    content: str
    parent_id: Optional[str] = None
    children: List["Section"] = Field(default_factory=list)
    chunk_type: ChunkType
    position: int


class RetrievalResult(BaseModel):
    """Result from vector search"""

    chunk_id: uuid.UUID
    section_id: str
    content: str
    similarity: float
    parent_content: Optional[str] = None
    sibling_contents: List[str] = Field(default_factory=list)


class PIIEntity(BaseModel):
    """Detected PII entity"""

    entity_type: str  # PERSON, ORG, LOCATION, etc.
    text: str
    start: int
    end: int
    confidence: float
    placeholder: str  # <PERSON_1>, <ORG_1>, etc.


class PIIMapping(BaseModel):
    """PII anonymization mapping"""

    request_id: str
    mappings: Dict[str, str]  # {placeholder: original}
    created_at: datetime
    ttl_seconds: int = 300


# Update forward references
Section.model_rebuild()
