"""
ABOUTME: FastAPI routes for JuraGPT document analysis API
ABOUTME: Integrates parser, PII anonymization, RAG, Gemini, and verification layers
"""

import hashlib
import time
import uuid
from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, Response
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from app.auth.middleware import require_auth
from app.auth.models import User
from app.auth.rate_limit import rate_limiter
from app.auth.usage import usage_tracker
from app.config import settings
from app.core.document_parser import DocumentParser
from app.core.docx_extractor import docx_extractor
from app.core.email_extractor import email_extractor
from app.core.file_detector import FileType, file_detector
from app.core.gemini_client import gemini_client
from app.core.local_verifier import local_verifier
from app.core.pdf_extractor import pdf_extractor
from app.core.pii_anonymizer import pii_anonymizer
from app.core.retriever import retriever
from app.core.text_merger import text_merger
from app.core.verifier import verifier
from app.utils.validators import validate_file, sanitize_query, validate_uuid, validate_top_k
from app.db.models import (
    AnalyzeRequest,
    AnalyzeResponse,
    DocumentIndexResponse,
    QueryLogDB,
)
from app.db.supabase_client import supabase_client
from app.services.modal_client import modal_ocr_client
from app.utils.file_storage import file_storage
from app.utils.logging import log_error, log_request, logger
from app.utils.redis_client import redis_client

router = APIRouter()


# Health check endpoint
@router.get("/health")
async def health_check():
    """Check API and dependencies health"""
    health_status = {
        "status": "healthy",
        "redis": redis_client.health_check(),
        "supabase": "connected",  # Simplified check
        "timestamp": time.time(),
    }

    if not health_status["redis"]:
        health_status["status"] = "degraded"

    return health_status


# Prometheus metrics endpoint
@router.get("/metrics")
async def metrics():
    """
    Expose Prometheus metrics for monitoring

    This endpoint is public (no auth required) to allow Prometheus to scrape it
    without authentication. In production, use network-level security (firewall)
    to restrict access to your monitoring infrastructure.
    """
    # Update Redis pool stats before serving metrics
    try:
        from app.utils.redis_client import redis_client
        from app.utils.metrics import metrics_manager

        pool_stats = redis_client.get_pool_stats()
        metrics_manager.update_redis_pool_stats(pool_stats)
    except Exception:
        # Don't fail metrics endpoint if Redis is unavailable
        pass

    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


# Cache management endpoint
@router.post("/admin/cache/clear")
async def clear_cache(
    pattern: str = "*",
    user: User = Depends(require_auth)
):
    """
    Clear cache entries matching pattern

    Args:
        pattern: Redis cache key pattern (default: "*" = clear all)
                 Examples: "query:*", "doc:123abc*", "cache:*"

    Returns:
        Number of cache entries cleared

    Security: Requires authentication
    """
    if not settings.cache_enabled:
        raise HTTPException(status_code=400, detail="Cache is disabled")

    try:
        cleared_count = redis_client.invalidate_cache(pattern)
        logger.info(
            f"Cache cleared by admin",
            extra={"pattern": pattern, "cleared_count": cleared_count, "user_id": str(user.id)},
        )

        return {
            "status": "success",
            "pattern": pattern,
            "cleared_count": cleared_count,
            "message": f"Cleared {cleared_count} cache entries matching '{pattern}'",
        }

    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        raise HTTPException(status_code=500, detail=f"Cache clear failed: {str(e)}")


# Document indexing endpoint
@router.post("/index", response_model=DocumentIndexResponse)
async def index_document(file: UploadFile = File(...), user: User = Depends(require_auth)):
    """
    Parse and index a legal document

    Steps:
    1. Read and hash document
    2. Parse into hierarchical sections
    3. Generate embeddings
    4. Store in database

    Implementation delegated to DocumentIndexerService for clean separation of concerns.
    """
    from app.services.document_indexer import document_indexer

    request_id = str(uuid.uuid4())
    result = await document_indexer.index_document(file, user, request_id)

    return DocumentIndexResponse(**result)


# Document analysis endpoint
@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_document(request: AnalyzeRequest, user: User = Depends(require_auth)):
    """
    Analyze document with PII-protected RAG pipeline

    Pipeline:
    1. Retrieve relevant chunks
    2. Anonymize PII in query and context
    3. Call Gemini for analysis
    4. De-anonymize response
    5. Verify citations
    6. Return structured response
    """
    request_id = str(uuid.uuid4())
    start_time = time.time()

    try:
        # Enforce rate limit and quota
        await rate_limiter.enforce_rate_limit(str(user.id), "analyze")
        await usage_tracker.enforce_quota(user.id, "queries", 1)

        # Validate inputs (security: UUID format, query sanitization, top_k range)
        document_id = validate_uuid(request.file_id, "file_id")
        sanitized_query = sanitize_query(request.query)
        validated_top_k = validate_top_k(request.top_k, default=settings.default_top_k)

        log_request(request_id=request_id, document_id=str(document_id), action="analyze_document")

        # 1. Verify document exists
        document = await supabase_client.get_document(document_id)
        if not document:
            raise HTTPException(status_code=404, detail="Document not found")

        # 2. Retrieve relevant chunks with hierarchical context
        logger.info("Retrieving relevant chunks...")
        retrieval_results = await retriever.retrieve(
            query=sanitized_query, document_id=document_id, top_k=validated_top_k
        )

        if not retrieval_results:
            raise HTTPException(status_code=404, detail="No relevant sections found for query")

        # 3. Format context for LLM
        context = retriever.format_context(retrieval_results)

        # 4. Anonymize PII in both query and context
        logger.info("Anonymizing PII...")
        anonymized_query, query_mapping = pii_anonymizer.anonymize(sanitized_query, request_id)
        anonymized_context, context_mapping = pii_anonymizer.anonymize(
            context, f"{request_id}_context"
        )

        # Verify no PII leakage
        if not pii_anonymizer.verify_no_pii_leakage(anonymized_query):
            logger.error("PII leakage detected in anonymized query")
            raise HTTPException(status_code=500, detail="PII protection failed")

        # 5. Call Gemini for analysis
        logger.info("Calling Gemini API...")
        gemini_response = gemini_client.analyze(
            query=anonymized_query, context=anonymized_context, request_id=request_id
        )

        # 6. De-anonymize response
        logger.info("De-anonymizing response...")
        final_answer = pii_anonymizer.deanonymize(gemini_response["answer"], request_id)

        # Clean up context PII mapping
        redis_client.delete_pii_mapping(f"{request_id}_context")

        # 7. Verify citations and detect hallucinations
        logger.info("Verifying citations...")

        # Use local verifier (GDPR-compliant) or fallback to Gemini
        if settings.use_local_verifier:
            llm_verification = local_verifier.verify_answer(
                answer=final_answer,
                context=context,  # Use original context (de-anonymized)
                request_id=request_id,
            )
        else:
            # Fallback to Gemini (not recommended for production)
            llm_verification = gemini_client.verify_answer(
                answer=final_answer, context=context, request_id=request_id
            )

        verification_result = verifier.verify_answer(
            answer=final_answer,
            retrieval_results=retrieval_results,
            gemini_verification=llm_verification,
        )

        # 8. Extract citations
        citations = verifier.extract_citations(final_answer, retrieval_results)

        # 9. Log query for audit trail
        latency_ms = int((time.time() - start_time) * 1000)

        await supabase_client.log_query(
            document_id=document_id,
            query_hash=hashlib.sha256(sanitized_query.encode()).hexdigest(),
            response_hash=hashlib.sha256(final_answer.encode()).hexdigest(),
            latency_ms=latency_ms,
            tokens_used=gemini_response.get("tokens_used"),
            model_version=gemini_response.get("model_version"),
            citations_count=len(citations),
            confidence_score=verification_result.confidence,
        )

        # Track token usage for user quota
        await usage_tracker.increment_usage(
            user.id, tokens=gemini_response.get("tokens_used", 0), queries=1
        )

        logger.info(
            "Analysis completed successfully",
            extra={
                "request_id": request_id,
                "document_id": str(document_id),
                "latency_ms": latency_ms,
                "citations_count": len(citations),
                "confidence": verification_result.confidence,
            },
        )

        # 10. Return structured response
        return AnalyzeResponse(
            answer=final_answer,
            citations=citations,
            confidence=verification_result.confidence,
            request_id=request_id,
            unsupported_claims=verification_result.unsupported_statements,
            metadata={
                "latency_ms": latency_ms,
                "tokens_used": gemini_response.get("tokens_used"),
                "chunks_retrieved": len(retrieval_results),
                "model_version": gemini_response.get("model_version"),
                "pii_entities_anonymized": len(query_mapping) if query_mapping else 0,
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        log_error(e, request_id=request_id)
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


# Query history endpoint
@router.get("/history/{document_id}", response_model=List[QueryLogDB])
async def get_query_history(document_id: str, limit: int = 50):
    """
    Get query history for a document (PII-free audit trail)
    """
    try:
        doc_uuid = uuid.UUID(document_id)
        logs = await supabase_client.get_query_logs(document_id=doc_uuid, limit=limit)
        return logs

    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid document ID")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch history: {str(e)}")


# Document list endpoint
@router.get("/documents")
async def list_documents(user_id: str = "default-user"):
    """List all documents for a user"""
    try:
        user_uuid = uuid.UUID(user_id) if user_id != "default-user" else uuid.uuid4()
        documents = await supabase_client.get_documents_by_user(user_uuid)
        return documents

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list documents: {str(e)}")
