"""
ABOUTME: Metrics middleware for automatic HTTP request tracking
ABOUTME: Integrates with Prometheus to collect performance data
"""

import time
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.utils.metrics import metrics_manager


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware to track HTTP request metrics"""

    async def dispatch(self, request: Request, call_next):
        """Track request duration and status code"""
        start_time = time.time()

        # Process request
        response: Response = await call_next(request)

        # Calculate duration
        duration = time.time() - start_time

        # Track metrics
        metrics_manager.track_request(
            method=request.method,
            endpoint=request.url.path,
            status_code=response.status_code,
            duration=duration,
        )

        return response
