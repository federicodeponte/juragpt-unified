"""
ABOUTME: Main FastAPI application entry point for JuraGPT backend
ABOUTME: Configures middleware, CORS, and routes
"""

import time
import uuid
from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration

from app.api.routes import router
from app.config import settings
from app.middleware.metrics import MetricsMiddleware
from app.middleware.security import SecurityHeadersMiddleware
from app.utils.logging import logger
from app.utils.metrics import metrics_manager

# Initialize Sentry (if DSN is configured)
if settings.sentry_dsn:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.sentry_environment or settings.environment,
        traces_sample_rate=settings.sentry_traces_sample_rate,
        profiles_sample_rate=settings.sentry_profiles_sample_rate,
        integrations=[
            StarletteIntegration(transaction_style="endpoint"),
            FastApiIntegration(transaction_style="endpoint"),
        ],
        # Performance monitoring
        enable_tracing=True,
        # Release tracking (optional - set via env var SENTRY_RELEASE)
        # release="juragpt@1.0.0",
        # Send PII to Sentry? False for GDPR compliance
        send_default_pii=False,
        # Sample rate for errors (1.0 = all errors)
        sample_rate=1.0,
        # Attach stack traces
        attach_stacktrace=True,
        # Max breadcrumbs to store
        max_breadcrumbs=50,
    )
    logger.info(f"Sentry initialized for environment: {settings.sentry_environment or settings.environment}")


# Lifespan context manager (replaces deprecated @app.on_event)
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events

    Replaces deprecated @app.on_event("startup") and @app.on_event("shutdown")
    See: https://fastapi.tiangolo.com/advanced/events/
    """
    # Startup
    logger.info("=" * 80)
    logger.info("JuraGPT API Starting...")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Log Level: {settings.log_level}")
    logger.info(f"Gemini Model: {settings.gemini_model}")
    logger.info(f"Embedding Model: {settings.embedding_model}")
    logger.info("=" * 80)

    # Initialize metrics
    metrics_manager.set_app_info(
        version="1.0.0",
        environment=settings.environment,
        model=settings.embedding_model,
    )
    logger.info("Prometheus metrics initialized")

    # Preload embedding model (avoids first-request latency)
    from app.core.retriever import get_retriever
    retriever = get_retriever()
    logger.info(
        f"Embedding model preloaded: {retriever.embedder.model_name} "
        f"(dimension: {retriever.embedder.embedding_dim})"
    )

    yield  # Application runs here

    # Shutdown
    logger.info("JuraGPT API shutting down...")

    # Close Redis connection pool
    from app.utils.redis_client import redis_client
    redis_client.close_pool()


# Create FastAPI app with lifespan
app = FastAPI(
    title="JuraGPT API",
    description="Legal document analysis API with PII protection and hierarchical RAG",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)


# Metrics middleware (first, to track all requests)
app.add_middleware(MetricsMiddleware)

# Security headers middleware (after metrics, before CORS)
app.add_middleware(SecurityHeadersMiddleware)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request ID middleware
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """Add unique request ID to all requests"""
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id

    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id

    return response


# Logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all requests with timing"""
    start_time = time.time()

    response = await call_next(request)

    latency_ms = int((time.time() - start_time) * 1000)

    logger.info(
        f"{request.method} {request.url.path}",
        extra={
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "latency_ms": latency_ms,
            "request_id": getattr(request.state, "request_id", None),
        },
    )

    return response


# Exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler"""
    request_id = getattr(request.state, "request_id", "unknown")

    logger.error(
        f"Unhandled exception: {str(exc)}", extra={"request_id": request_id}, exc_info=True
    )

    return JSONResponse(
        status_code=500, content={"detail": "Internal server error", "request_id": request_id}
    )


# Include API routes
app.include_router(router, prefix=settings.api_v1_prefix)


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint"""
    return {"service": "JuraGPT API", "version": "1.0.0", "status": "running", "docs": "/docs"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True if settings.environment == "development" else False,
        log_level=settings.log_level.lower(),
    )
