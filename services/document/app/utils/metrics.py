"""
ABOUTME: Prometheus metrics for monitoring application performance
ABOUTME: Tracks requests, latency, errors, and business metrics
"""

from prometheus_client import Counter, Gauge, Histogram, Info
from typing import Dict

# ============================================================================
# HTTP METRICS
# ============================================================================

# Request counters
http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "endpoint", "status_code"],
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint"],
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.5, 5.0, 10.0),
)

# ============================================================================
# BUSINESS METRICS
# ============================================================================

# Document metrics
documents_indexed_total = Counter(
    "documents_indexed_total",
    "Total documents indexed",
    ["user_id", "file_type"],
)

document_indexing_duration_seconds = Histogram(
    "document_indexing_duration_seconds",
    "Document indexing latency in seconds",
    ["file_type"],
    buckets=(1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0),
)

document_size_bytes = Histogram(
    "document_size_bytes",
    "Document file size in bytes",
    ["file_type"],
    buckets=(1024, 10240, 102400, 1048576, 10485760, 104857600),  # 1KB to 100MB
)

chunks_created_total = Counter(
    "chunks_created_total",
    "Total chunks created from documents",
    ["document_id"],
)

# Query metrics
queries_total = Counter(
    "queries_total",
    "Total queries processed",
    ["user_id", "document_id"],
)

query_latency_seconds = Histogram(
    "query_latency_seconds",
    "Query processing latency in seconds",
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0),
)

query_confidence_score = Histogram(
    "query_confidence_score",
    "Query answer confidence score",
    buckets=(0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95, 1.0),
)

retrieval_chunks_returned = Histogram(
    "retrieval_chunks_returned",
    "Number of chunks returned from retrieval",
    buckets=(1, 3, 5, 10, 20, 50),
)

# ============================================================================
# MODEL METRICS
# ============================================================================

# Embedding generation
embedding_generation_duration_seconds = Histogram(
    "embedding_generation_duration_seconds",
    "Embedding generation latency in seconds",
    ["model"],
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0),
)

embeddings_generated_total = Counter(
    "embeddings_generated_total",
    "Total embeddings generated",
    ["model"],
)

# LLM metrics
llm_requests_total = Counter(
    "llm_requests_total",
    "Total LLM API requests",
    ["provider", "model"],
)

llm_tokens_used_total = Counter(
    "llm_tokens_used_total",
    "Total LLM tokens consumed",
    ["provider", "model"],
)

llm_latency_seconds = Histogram(
    "llm_latency_seconds",
    "LLM API latency in seconds",
    ["provider", "model"],
    buckets=(0.5, 1.0, 2.0, 5.0, 10.0, 30.0),
)

# OCR metrics
ocr_requests_total = Counter(
    "ocr_requests_total",
    "Total OCR requests",
    ["provider"],
)

ocr_pages_processed_total = Counter(
    "ocr_pages_processed_total",
    "Total pages processed via OCR",
    ["provider"],
)

ocr_confidence_score = Histogram(
    "ocr_confidence_score",
    "OCR confidence score",
    ["provider"],
    buckets=(0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95, 1.0),
)

# ============================================================================
# PII METRICS
# ============================================================================

pii_entities_detected_total = Counter(
    "pii_entities_detected_total",
    "Total PII entities detected",
    ["entity_type"],
)

pii_anonymization_duration_seconds = Histogram(
    "pii_anonymization_duration_seconds",
    "PII anonymization latency in seconds",
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0),
)

# ============================================================================
# ERROR METRICS
# ============================================================================

errors_total = Counter(
    "errors_total",
    "Total errors by type and severity",
    ["error_type", "severity", "endpoint"],
)

rate_limit_hits_total = Counter(
    "rate_limit_hits_total",
    "Total rate limit hits",
    ["user_id", "endpoint"],
)

# ============================================================================
# SYSTEM METRICS
# ============================================================================

# Database
db_connections_active = Gauge(
    "db_connections_active",
    "Number of active database connections",
)

db_query_duration_seconds = Histogram(
    "db_query_duration_seconds",
    "Database query latency in seconds",
    ["operation"],
    buckets=(0.001, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0),
)

# Redis
redis_operations_total = Counter(
    "redis_operations_total",
    "Total Redis operations",
    ["operation", "status"],
)

redis_operation_duration_seconds = Histogram(
    "redis_operation_duration_seconds",
    "Redis operation latency in seconds",
    ["operation"],
    buckets=(0.001, 0.005, 0.01, 0.05, 0.1),
)

redis_pool_connections_in_use = Gauge(
    "redis_pool_connections_in_use",
    "Number of Redis connections currently in use",
)

redis_pool_connections_available = Gauge(
    "redis_pool_connections_available",
    "Number of Redis connections available in pool",
)

redis_pool_connections_max = Gauge(
    "redis_pool_connections_max",
    "Maximum number of Redis connections in pool",
)

# Cache metrics
cache_hits_total = Counter(
    "cache_hits_total",
    "Total cache hits",
    ["cache_type"],  # query_results, documents, query_logs
)

cache_misses_total = Counter(
    "cache_misses_total",
    "Total cache misses",
    ["cache_type"],
)

cache_hit_ratio = Gauge(
    "cache_hit_ratio",
    "Cache hit ratio (0.0 to 1.0)",
    ["cache_type"],
)

cache_entries_total = Gauge(
    "cache_entries_total",
    "Total number of cached entries",
    ["cache_type"],
)

# Application info
app_info = Info(
    "app_info",
    "Application metadata",
)


class MetricsManager:
    """Central manager for application metrics"""

    @staticmethod
    def set_app_info(version: str, environment: str, model: str):
        """Set application metadata"""
        app_info.info(
            {
                "version": version,
                "environment": environment,
                "embedding_model": model,
            }
        )

    @staticmethod
    def track_request(method: str, endpoint: str, status_code: int, duration: float):
        """Track HTTP request"""
        http_requests_total.labels(
            method=method, endpoint=endpoint, status_code=status_code
        ).inc()
        http_request_duration_seconds.labels(method=method, endpoint=endpoint).observe(
            duration
        )

    @staticmethod
    def track_document_index(
        user_id: str, file_type: str, file_size: int, duration: float, chunks: int
    ):
        """Track document indexing"""
        documents_indexed_total.labels(user_id=user_id, file_type=file_type).inc()
        document_indexing_duration_seconds.labels(file_type=file_type).observe(duration)
        document_size_bytes.labels(file_type=file_type).observe(file_size)

    @staticmethod
    def track_query(
        user_id: str,
        document_id: str,
        duration: float,
        confidence: float,
        chunks_returned: int,
    ):
        """Track query processing"""
        queries_total.labels(user_id=user_id, document_id=document_id).inc()
        query_latency_seconds.observe(duration)
        query_confidence_score.observe(confidence)
        retrieval_chunks_returned.observe(chunks_returned)

    @staticmethod
    def track_llm_request(
        provider: str, model: str, duration: float, tokens_used: int
    ):
        """Track LLM API request"""
        llm_requests_total.labels(provider=provider, model=model).inc()
        llm_tokens_used_total.labels(provider=provider, model=model).inc(tokens_used)
        llm_latency_seconds.labels(provider=provider, model=model).observe(duration)

    @staticmethod
    def track_ocr_request(
        provider: str, pages_processed: int, avg_confidence: float
    ):
        """Track OCR request"""
        ocr_requests_total.labels(provider=provider).inc()
        ocr_pages_processed_total.labels(provider=provider).inc(pages_processed)
        ocr_confidence_score.labels(provider=provider).observe(avg_confidence)

    @staticmethod
    def track_pii_anonymization(entity_count: Dict[str, int], duration: float):
        """Track PII anonymization"""
        for entity_type, count in entity_count.items():
            pii_entities_detected_total.labels(entity_type=entity_type).inc(count)
        pii_anonymization_duration_seconds.observe(duration)

    @staticmethod
    def track_error(error_type: str, severity: str, endpoint: str):
        """Track error occurrence"""
        errors_total.labels(
            error_type=error_type, severity=severity, endpoint=endpoint
        ).inc()

    @staticmethod
    def track_rate_limit_hit(user_id: str, endpoint: str):
        """Track rate limit hit"""
        rate_limit_hits_total.labels(user_id=user_id, endpoint=endpoint).inc()

    @staticmethod
    def track_db_query(operation: str, duration: float):
        """Track database query"""
        db_query_duration_seconds.labels(operation=operation).observe(duration)

    @staticmethod
    def track_redis_operation(operation: str, status: str, duration: float):
        """Track Redis operation"""
        redis_operations_total.labels(operation=operation, status=status).inc()
        redis_operation_duration_seconds.labels(operation=operation).observe(duration)

    @staticmethod
    def update_redis_pool_stats(stats: Dict[str, int]):
        """
        Update Redis connection pool metrics

        Args:
            stats: Dictionary with keys: in_use_connections, available_connections, max_connections
        """
        redis_pool_connections_in_use.set(stats.get("in_use_connections", 0))
        redis_pool_connections_available.set(stats.get("available_connections", 0))
        redis_pool_connections_max.set(stats.get("max_connections", 0))


# Global metrics manager instance
metrics_manager = MetricsManager()
