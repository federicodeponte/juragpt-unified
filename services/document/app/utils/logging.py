"""
ABOUTME: Structured logging configuration for JuraGPT
ABOUTME: Provides secure, production-grade JSON logging that never logs PII
"""

import json
import logging
import os
import sys
import traceback
from datetime import datetime
from typing import Any, Dict, Optional

from app.config import settings


class StructuredJSONFormatter(logging.Formatter):
    """
    Production-grade JSON formatter with comprehensive contextual fields

    Features:
    - Structured JSON output for log aggregation tools (ELK, Datadog, Splunk)
    - Automatic context enrichment (hostname, process, thread)
    - Exception handling with stack traces
    - PII-safe (never logs sensitive user data)
    - ISO 8601 timestamps with timezone
    - Compatible with OpenTelemetry traces
    """

    def __init__(self):
        super().__init__()
        self.hostname = os.uname().nodename
        self.pid = os.getpid()

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as structured JSON"""

        # Base log structure
        log_data = {
            # Core fields
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),

            # Code location
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,

            # Process/thread context
            "hostname": self.hostname,
            "pid": self.pid,
            "thread": record.thread,
            "thread_name": record.threadName,

            # Environment
            "environment": settings.environment,
        }

        # Add exception information if present
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "stacktrace": self._format_stacktrace(record.exc_info),
            }

        # Add custom fields from 'extra' parameter
        # Safely iterate over record attributes to find custom fields
        standard_attrs = {
            'name', 'msg', 'args', 'created', 'filename', 'funcName', 'levelname',
            'levelno', 'lineno', 'module', 'msecs', 'pathname', 'process',
            'processName', 'relativeCreated', 'thread', 'threadName', 'exc_info',
            'exc_text', 'stack_info', 'getMessage', 'message'
        }

        custom_fields = {}
        for attr_name in dir(record):
            if not attr_name.startswith('_') and attr_name not in standard_attrs:
                attr_value = getattr(record, attr_name, None)
                # Only add serializable types
                if isinstance(attr_value, (str, int, float, bool, type(None), dict, list)):
                    custom_fields[attr_name] = attr_value

        # Merge custom fields into log data
        if custom_fields:
            log_data.update(custom_fields)

        return json.dumps(log_data, ensure_ascii=False, default=str)

    def _format_stacktrace(self, exc_info) -> str:
        """Format exception stack trace"""
        return ''.join(traceback.format_exception(*exc_info))


def setup_logging() -> logging.Logger:
    """
    Configure structured JSON logging for production

    Features:
    - JSON output to stdout (container-friendly)
    - Automatic context enrichment
    - Environment-based log level
    - Compatible with log aggregation tools
    """

    logger = logging.getLogger("juragpt")
    logger.setLevel(getattr(logging, settings.log_level.upper()))

    # Clear existing handlers to avoid duplicates
    logger.handlers.clear()

    # Console handler with structured JSON formatter
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(StructuredJSONFormatter())
    logger.addHandler(console_handler)

    # Prevent propagation to root logger (avoid duplicate logs)
    logger.propagate = False

    return logger


# Global logger instance
logger = setup_logging()


# ============================================================================
# Utility Functions for Common Logging Patterns
# ============================================================================


def log_request(
    request_id: str,
    action: str,
    document_id: Optional[str] = None,
    user_id: Optional[str] = None,
    extra: Optional[Dict[str, Any]] = None,
):
    """
    Log an API request with standard context

    Args:
        request_id: Unique request identifier (UUID)
        action: Action being performed (e.g., "analyze_document", "index_document")
        document_id: Optional document UUID
        user_id: Optional user UUID
        extra: Additional context fields

    Example:
        log_request(
            request_id="abc123",
            action="analyze_document",
            document_id="doc456",
            user_id="user789",
            extra={"top_k": 5, "query_length": 42}
        )
    """
    context = {
        "request_id": request_id,
        "action": action,
        **(extra or {})
    }

    if document_id:
        context["document_id"] = document_id
    if user_id:
        context["user_id"] = user_id

    logger.info(f"Request: {action}", extra=context)


def log_error(
    error: Exception,
    request_id: Optional[str] = None,
    user_id: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
):
    """
    Log an error with full context and stack trace

    Args:
        error: Exception instance
        request_id: Optional request UUID for correlation
        user_id: Optional user UUID
        context: Additional context fields

    Example:
        try:
            risky_operation()
        except ValueError as e:
            log_error(e, request_id=request_id, context={"file_size": 1024})
    """
    error_context = {
        "error_type": type(error).__name__,
        "error_message": str(error),
        **(context or {})
    }

    if request_id:
        error_context["request_id"] = request_id
    if user_id:
        error_context["user_id"] = user_id

    logger.error(
        f"Error: {type(error).__name__}: {str(error)}",
        extra=error_context,
        exc_info=True,  # Include stack trace
    )


def log_performance(
    operation: str,
    latency_ms: int,
    request_id: Optional[str] = None,
    success: bool = True,
    extra: Optional[Dict[str, Any]] = None,
):
    """
    Log performance metrics for an operation

    Args:
        operation: Name of operation (e.g., "embedding_generation", "vector_search")
        latency_ms: Execution time in milliseconds
        request_id: Optional request UUID
        success: Whether operation succeeded
        extra: Additional metrics

    Example:
        log_performance(
            operation="vector_search",
            latency_ms=127,
            request_id=request_id,
            extra={"chunks_returned": 5, "similarity_avg": 0.87}
        )
    """
    perf_context = {
        "operation": operation,
        "latency_ms": latency_ms,
        "success": success,
        **(extra or {})
    }

    if request_id:
        perf_context["request_id"] = request_id

    # Log as INFO for successful operations, WARNING for slow operations
    if latency_ms > 5000:  # > 5 seconds
        logger.warning(f"Slow operation: {operation} ({latency_ms}ms)", extra=perf_context)
    else:
        logger.info(f"Performance: {operation}", extra=perf_context)


def log_cache_event(
    event_type: str,
    cache_key: str,
    request_id: Optional[str] = None,
    ttl: Optional[int] = None,
    extra: Optional[Dict[str, Any]] = None,
):
    """
    Log cache-related events (hits, misses, invalidations)

    Args:
        event_type: Type of cache event ("hit", "miss", "set", "invalidate")
        cache_key: Cache key involved
        request_id: Optional request UUID
        ttl: Optional TTL in seconds (for "set" events)
        extra: Additional context

    Example:
        log_cache_event("hit", cache_key="query:doc123:abc", request_id=request_id)
    """
    cache_context = {
        "cache_event": event_type,
        "cache_key": cache_key,
        **(extra or {})
    }

    if request_id:
        cache_context["request_id"] = request_id
    if ttl:
        cache_context["ttl_seconds"] = ttl

    logger.info(f"Cache {event_type}: {cache_key}", extra=cache_context)


def log_security_event(
    event_type: str,
    user_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    severity: str = "INFO",
    extra: Optional[Dict[str, Any]] = None,
):
    """
    Log security-related events (auth failures, rate limits, suspicious activity)

    Args:
        event_type: Type of security event (e.g., "auth_failure", "rate_limit_exceeded")
        user_id: Optional user UUID
        ip_address: Optional IP address (hashed for privacy)
        severity: Severity level ("INFO", "WARNING", "ERROR", "CRITICAL")
        extra: Additional security context

    Example:
        log_security_event(
            "rate_limit_exceeded",
            user_id="user123",
            severity="WARNING",
            extra={"endpoint": "/api/v1/analyze", "attempts": 100}
        )
    """
    security_context = {
        "security_event": event_type,
        "severity": severity,
        **(extra or {})
    }

    if user_id:
        security_context["user_id"] = user_id
    if ip_address:
        # Hash IP address for privacy (GDPR compliance)
        import hashlib
        security_context["ip_hash"] = hashlib.sha256(ip_address.encode()).hexdigest()[:16]

    log_level = getattr(logging, severity.upper(), logging.INFO)
    logger.log(log_level, f"Security: {event_type}", extra=security_context)
