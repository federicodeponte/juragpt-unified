"""
ABOUTME: Rate limiting middleware for API protection
ABOUTME: Implements sliding window rate limiting per IP/API key
"""

import logging
import time
from collections import defaultdict, deque
from typing import Deque, Dict, Optional, Tuple

from fastapi import HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from auditor.config.settings import get_settings

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Sliding window rate limiter.

    Tracks requests per client (IP or API key) and enforces limits.
    """

    def __init__(self, requests_per_minute: int = 60, burst_size: int = 10):
        """
        Initialize rate limiter.

        Args:
            requests_per_minute: Maximum requests allowed per minute
            burst_size: Maximum burst requests allowed
        """
        self.requests_per_minute = requests_per_minute
        self.burst_size = burst_size
        self.window_size = 60  # 1 minute window

        # Store timestamps of requests per client
        # Key: client_id, Value: deque of timestamps
        self._requests: Dict[str, Deque[float]] = defaultdict(deque)

        logger.info(
            f"Rate limiter initialized: {requests_per_minute} req/min, "
            f"burst: {burst_size}"
        )

    def _clean_old_requests(self, client_id: str, current_time: float) -> None:
        """Remove requests older than the window"""
        cutoff_time = current_time - self.window_size

        while (
            self._requests[client_id]
            and self._requests[client_id][0] < cutoff_time
        ):
            self._requests[client_id].popleft()

    def check_rate_limit(
        self,
        client_id: str,
        custom_limit: Optional[int] = None
    ) -> Tuple[bool, Dict[str, any]]:
        """
        Check if a request should be rate limited.

        Args:
            client_id: Unique identifier for the client (IP or API key)
            custom_limit: Custom rate limit for this client (overrides default)

        Returns:
            Tuple of (is_allowed, info_dict)
            - is_allowed: True if request is allowed, False if rate limited
            - info_dict: Dict with rate limit info (used for headers)
        """
        current_time = time.time()
        limit = custom_limit or self.requests_per_minute

        # Clean old requests
        self._clean_old_requests(client_id, current_time)

        # Get request count in current window
        request_count = len(self._requests[client_id])

        # Check burst limit (last second)
        recent_cutoff = current_time - 1.0
        recent_count = sum(
            1 for ts in self._requests[client_id]
            if ts > recent_cutoff
        )

        # Rate limit info
        info = {
            "limit": limit,
            "remaining": max(0, limit - request_count),
            "reset": int(current_time + self.window_size),
            "retry_after": None
        }

        # Check burst limit first
        if recent_count >= self.burst_size:
            logger.warning(
                f"Burst limit exceeded for {client_id}: "
                f"{recent_count}/{self.burst_size} in 1s"
            )
            info["retry_after"] = 1
            return False, info

        # Check per-minute limit
        if request_count >= limit:
            oldest_request = self._requests[client_id][0]
            retry_after = int(oldest_request + self.window_size - current_time) + 1

            logger.warning(
                f"Rate limit exceeded for {client_id}: "
                f"{request_count}/{limit} in {self.window_size}s"
            )
            info["retry_after"] = retry_after
            return False, info

        # Allow request and record it
        self._requests[client_id].append(current_time)
        info["remaining"] = limit - len(self._requests[client_id])

        return True, info

    def get_stats(self, client_id: str) -> Dict[str, any]:
        """Get current rate limit stats for a client"""
        current_time = time.time()
        self._clean_old_requests(client_id, current_time)

        return {
            "client_id": client_id,
            "requests_in_window": len(self._requests[client_id]),
            "limit": self.requests_per_minute,
            "window_size": self.window_size
        }


# Global rate limiter instance
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Get or create the global rate limiter instance"""
    global _rate_limiter

    if _rate_limiter is None:
        settings = get_settings()
        _rate_limiter = RateLimiter(
            requests_per_minute=settings.rate_limit_per_minute,
            burst_size=settings.rate_limit_burst
        )

    return _rate_limiter


def get_client_id(request: Request) -> str:
    """
    Get unique client identifier from request.

    Prefers API key, falls back to IP address.

    Args:
        request: FastAPI request object

    Returns:
        Unique client identifier
    """
    # Check for API key first
    api_key = request.headers.get("X-API-Key")
    if api_key:
        # Use a hash of the API key to avoid storing full keys
        import hashlib
        return f"key:{hashlib.sha256(api_key.encode()).hexdigest()[:16]}"

    # Fall back to IP address
    # Check X-Forwarded-For for proxied requests
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Use first IP in the chain
        client_ip = forwarded_for.split(",")[0].strip()
    else:
        client_ip = request.client.host if request.client else "unknown"

    return f"ip:{client_ip}"


def get_custom_rate_limit(request: Request) -> Optional[int]:
    """
    Get custom rate limit for the request (from API key metadata).

    Args:
        request: FastAPI request object

    Returns:
        Custom rate limit if available, None otherwise
    """
    # This would be retrieved from API key metadata in production
    # For now, return None to use default limits
    return None


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for rate limiting.

    Applies rate limits to all requests and returns appropriate headers.
    """

    async def dispatch(self, request: Request, call_next):
        """Process request with rate limiting"""
        settings = get_settings()

        # Skip rate limiting if disabled
        if not settings.enable_rate_limiting:
            return await call_next(request)

        # Skip rate limiting for health/metrics endpoints
        if request.url.path in ["/health", "/metrics", "/docs", "/openapi.json"]:
            return await call_next(request)

        limiter = get_rate_limiter()
        client_id = get_client_id(request)
        custom_limit = get_custom_rate_limit(request)

        # Check rate limit
        is_allowed, info = limiter.check_rate_limit(client_id, custom_limit)

        # Always add rate limit headers
        headers = {
            "X-RateLimit-Limit": str(info["limit"]),
            "X-RateLimit-Remaining": str(info["remaining"]),
            "X-RateLimit-Reset": str(info["reset"]),
        }

        if not is_allowed:
            # Rate limited - return 429
            if info["retry_after"]:
                headers["Retry-After"] = str(info["retry_after"])

            logger.warning(
                f"Rate limit exceeded: {client_id} "
                f"({info['remaining']}/{info['limit']})"
            )

            return Response(
                content='{"detail": "Rate limit exceeded. Please try again later."}',
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                headers=headers,
                media_type="application/json"
            )

        # Request allowed - proceed
        response = await call_next(request)

        # Add rate limit headers to response
        for key, value in headers.items():
            response.headers[key] = value

        return response
