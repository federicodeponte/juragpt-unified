"""
ABOUTME: FastAPI server for verification API
ABOUTME: Provides REST endpoints for LLM answer verification
"""

import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, AsyncIterator, Dict, List, Optional, cast

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.responses import Response

from auditor.api.models import (
    ErrorResponse,
    HealthResponse,
    MetricsResponse,
    VerifyRequest,
    VerifyResponse,
)
from auditor.config.settings import get_settings
from auditor.core.verification_service import VerificationService
from auditor.security import (
    CORSConfig,
    RateLimitMiddleware,
    SecurityHeadersMiddleware,
    get_current_user_flexible,
)
from auditor.storage.storage_interface import StorageInterface

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Prometheus metrics - use multiprocess mode to avoid duplicate registration
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Histogram,
    generate_latest,
)

# Create custom registry to avoid conflicts
prom_registry = CollectorRegistry()

VERIFY_REQUESTS = Counter(
    'auditor_verify_requests_total',
    'Total verification requests',
    ['status'],
    registry=prom_registry
)
VERIFY_LATENCY = Histogram(
    'auditor_verify_latency_seconds',
    'Verification request latency',
    registry=prom_registry
)
CONFIDENCE_DISTRIBUTION = Histogram(
    'auditor_confidence_score',
    'Distribution of confidence scores',
    buckets=[0.0, 0.2, 0.4, 0.6, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95, 1.0],
    registry=prom_registry
)

# Settings
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    Modern FastAPI lifespan context manager.

    Handles application startup and shutdown with proper async context management.
    Services are stored in app.state for dependency injection.
    """
    # Startup
    logger.info("🚀 Starting JuraGPT Auditor API")
    logger.info(f"   Sentence Threshold: {settings.sentence_threshold}")
    logger.info(f"   Overall Threshold: {settings.overall_threshold}")
    logger.info(f"   Auto-retry: {settings.auto_retry_enabled}")
    logger.info(f"   Database: {settings.database_url}")

    # Initialize services
    logger.info("Initializing verification service...")
    app.state.verification_service = VerificationService(settings=settings)
    logger.info("✓ Verification service ready")

    logger.info(f"Initializing storage: {settings.database_url}")
    app.state.storage = StorageInterface(database_url=settings.database_url)
    logger.info("✓ Storage ready")

    yield  # Server runs here

    # Shutdown (cleanup if needed in the future)
    logger.info("Shutting down JuraGPT Auditor API")


# Application with lifespan
app = FastAPI(
    title="JuraGPT Auditor",
    description="Sentence-level verification of LLM answers against legal sources",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Security middlewares
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RateLimitMiddleware)

# CORS middleware (configured based on environment)
cors_config = CORSConfig.get_cors_config()
app.add_middleware(CORSMiddleware, **cors_config)

# Include authentication routes
from auditor.api.auth_endpoints import router as auth_router
app.include_router(auth_router)


# Dependency injection functions
def get_verification_service(request: Request) -> VerificationService:
    """
    FastAPI dependency for verification service.

    Retrieves service from app.state (initialized in lifespan).
    """
    return cast(VerificationService, request.app.state.verification_service)


def get_storage(request: Request) -> StorageInterface:
    """
    FastAPI dependency for storage interface.

    Retrieves storage from app.state (initialized in lifespan).
    """
    return cast(StorageInterface, request.app.state.storage)


@app.get("/", response_model=Dict[str, str])
async def root() -> Dict[str, str]:
    """Root endpoint"""
    return {
        "service": "JuraGPT Auditor",
        "version": "0.1.0",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Health check endpoint.

    Returns service status and version.
    """
    return HealthResponse(
        status="healthy",
        version="0.1.0",
        timestamp=datetime.now().isoformat(),
    )


@app.post("/verify", response_model=VerifyResponse, responses={
    400: {"model": ErrorResponse},
    500: {"model": ErrorResponse}
})
async def verify_answer(
    request: VerifyRequest,
    service: VerificationService = Depends(get_verification_service),
    storage: StorageInterface = Depends(get_storage),
    current_user: Optional[Dict] = Depends(get_current_user_flexible),
) -> Dict[str, Any]:
    """
    Verify an LLM-generated answer against source snippets.

    This endpoint:
    1. Splits the answer into sentences
    2. Matches each sentence against sources using semantic similarity
    3. Calculates a confidence score
    4. Returns verification result with trust label

    Args:
        request: VerifyRequest with answer and sources
        service: Verification service (injected)
        storage: Storage interface (injected)

    Returns:
        VerifyResponse with verification results

    Raises:
        HTTPException: If verification fails
    """
    start_time = datetime.now()

    try:

        # Convert request to service format
        sources: List[Dict[str, Any]] = []
        for i, src in enumerate(request.sources):
            sources.append({
                "text": src.text,
                "source_id": src.source_id or f"source_{i}",
                "score": src.score if src.score is not None else 0.5,
            })

        # Verify
        user_info = f" (user: {current_user['user_id']})" if current_user else ""
        logger.info(f"Verifying answer ({len(request.answer)} chars, {len(sources)} sources){user_info}")
        # Note: verification_service.py types sources as Dict[str, str] but actually uses
        # numeric scores internally. This is a known type annotation issue in that module.
        result = service.verify(
            answer=request.answer,
            sources=sources,  # type: ignore[arg-type]
            metadata=request.metadata,
        )

        # Store result
        storage.store_verification(result)

        # Record metrics
        VERIFY_REQUESTS.labels(status='success').inc()
        CONFIDENCE_DISTRIBUTION.observe(result["confidence"]["score"])

        # Calculate latency
        latency = (datetime.now() - start_time).total_seconds()
        VERIFY_LATENCY.observe(latency)

        logger.info(
            f"✓ Verification complete: {result['verification_id']} "
            f"(confidence: {result['confidence']['score']:.2f}, "
            f"label: {result['confidence']['trust_label']})"
        )

        return result

    except Exception as e:
        VERIFY_REQUESTS.labels(status='error').inc()
        logger.error(f"Verification failed: {str(e)}", exc_info=True)

        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error="Verification failed",
                detail=str(e)
            ).dict()
        )


@app.get("/metrics")
async def metrics() -> Response:
    """
    Prometheus metrics endpoint.

    Returns metrics in Prometheus format.
    """
    if not settings.enable_metrics:
        raise HTTPException(status_code=404, detail="Metrics disabled")

    return Response(content=generate_latest(prom_registry), media_type=CONTENT_TYPE_LATEST)


@app.get("/statistics", response_model=MetricsResponse)
async def get_statistics(storage: StorageInterface = Depends(get_storage)) -> MetricsResponse:
    """
    Get service statistics.

    Returns aggregated statistics about verifications.

    Args:
        storage: Storage interface (injected)
    """
    try:
        stats = storage.get_statistics()

        return MetricsResponse(
            total_verifications=stats["total_verifications"],
            valid_verifications=stats["valid_verifications"],
            average_confidence=stats["average_confidence"],
            by_label=stats["by_label"],
        )

    except Exception as e:
        logger.error(f"Failed to get statistics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/verifications/{verification_id}")
async def get_verification(
    verification_id: str,
    storage: StorageInterface = Depends(get_storage),
) -> Dict[str, Any]:
    """
    Retrieve a specific verification result by ID.

    Args:
        verification_id: Verification UUID
        storage: Storage interface (injected)

    Returns:
        Verification result dict

    Raises:
        HTTPException: If not found
    """
    try:
        result = storage.get_verification(verification_id)

        if not result:
            raise HTTPException(
                status_code=404,
                detail=f"Verification {verification_id} not found"
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to retrieve verification: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Global exception handler"""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)

    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error="Internal server error",
            detail=str(exc)
        ).dict()
    )


def main() -> None:
    """Run server with uvicorn"""
    import uvicorn

    uvicorn.run(
        "auditor.api.server:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_reload,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
