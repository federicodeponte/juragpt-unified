"""
ABOUTME: Pydantic models for API request/response validation
ABOUTME: Defines schemas for /verify endpoint and other API operations
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class SourceSnippet(BaseModel):
    """Source snippet for verification"""

    text: str = Field(..., description="Source text content", min_length=1)
    source_id: Optional[str] = Field(None, description="Unique source identifier")
    score: Optional[float] = Field(None, description="Retrieval score (0-1)", ge=0.0, le=1.0)


class VerifyRequest(BaseModel):
    """Request model for /verify endpoint"""

    answer: str = Field(..., description="Generated answer text to verify", min_length=1)
    sources: List[SourceSnippet] = Field(..., description="List of source snippets", min_items=1)
    metadata: Optional[Dict[str, Any]] = Field(None, description="Optional metadata")

    class Config:
        json_schema_extra = {
            "example": {
                "answer": "Nach § 823 BGB haftet, wer vorsätzlich oder fahrlässig einen Schaden verursacht.",
                "sources": [
                    {
                        "text": "Wer vorsätzlich oder fahrlässig das Leben... zum Ersatz verpflichtet.",
                        "source_id": "bgb_823_1",
                        "score": 0.95,
                    }
                ],
                "metadata": {"query_id": "q001", "user_id": "test_user"},
            }
        }


class AnswerInfo(BaseModel):
    """Information about the answer"""

    text: str
    total_sentences: int
    has_citations: bool
    citations: List[str]


class SourcesInfo(BaseModel):
    """Information about sources used"""

    count: int
    fingerprints: List[str]


class VerificationInfo(BaseModel):
    """Sentence-level verification info"""

    verified_sentences: int
    total_sentences: int
    verification_rate: float


class ConfidenceComponents(BaseModel):
    """Breakdown of confidence components"""

    semantic_similarity: float
    retrieval_quality: float
    citation_presence: float
    coverage: float


class ConfidenceInfo(BaseModel):
    """Confidence scoring information"""

    score: float = Field(..., ge=0.0, le=1.0)
    verified: bool
    trust_label: str
    components: ConfidenceComponents


class VerifyResponse(BaseModel):
    """Response model for /verify endpoint"""

    verification_id: str
    timestamp: str
    duration_ms: float

    answer: AnswerInfo
    sources: SourcesInfo
    verification: VerificationInfo
    confidence: ConfidenceInfo

    metadata: Optional[Dict[str, Any]] = None

    class Config:
        json_schema_extra = {
            "example": {
                "verification_id": "550e8400-e29b-41d4-a716-446655440000",
                "timestamp": "2024-01-15T10:30:00",
                "duration_ms": 234.5,
                "answer": {
                    "text": "Nach § 823 BGB haftet...",
                    "total_sentences": 2,
                    "has_citations": True,
                    "citations": ["§ 823 BGB"],
                },
                "sources": {"count": 1, "fingerprints": ["abc123"]},
                "verification": {
                    "verified_sentences": 2,
                    "total_sentences": 2,
                    "verification_rate": 1.0,
                },
                "confidence": {
                    "score": 0.89,
                    "verified": True,
                    "trust_label": "✅ Verified",
                    "components": {
                        "semantic_similarity": 0.91,
                        "retrieval_quality": 0.87,
                        "citation_presence": 0.85,
                        "coverage": 1.0,
                    },
                },
            }
        }


class HealthResponse(BaseModel):
    """Health check response"""

    status: str
    version: str
    timestamp: str


class MetricsResponse(BaseModel):
    """Metrics response"""

    total_verifications: int
    valid_verifications: int
    average_confidence: float
    by_label: Dict[str, int]


class ErrorResponse(BaseModel):
    """Error response"""

    error: str
    detail: Optional[str] = None
    verification_id: Optional[str] = None
