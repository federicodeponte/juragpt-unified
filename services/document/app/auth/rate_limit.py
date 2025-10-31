"""
ABOUTME: Simple rate limiting middleware using sliding window
ABOUTME: In-memory cache for fast lookups, can be replaced with Redis
"""

import time
from collections import defaultdict
from typing import Dict, Tuple

from fastapi import HTTPException, status


class RateLimiter:
    """Simple sliding window rate limiter"""

    def __init__(self):
        # user_id -> [(timestamp, count)]
        self.requests: Dict[str, list] = defaultdict(list)

        # Rate limits (requests per minute)
        self.limits = {
            "index": 10,  # 10 document uploads per minute
            "analyze": 60,  # 60 queries per minute
            "default": 100,  # 100 requests per minute for other endpoints
        }

    def _clean_old_requests(self, user_id: str, window_seconds: int = 60):
        """Remove requests older than window"""
        cutoff = time.time() - window_seconds
        self.requests[user_id] = [
            (ts, count) for ts, count in self.requests[user_id] if ts > cutoff
        ]

    def check_rate_limit(self, user_id: str, endpoint: str = "default") -> Tuple[bool, int]:
        """
        Check if request is within rate limit

        Returns:
            (allowed: bool, remaining: int)
        """
        self._clean_old_requests(user_id)

        limit = self.limits.get(endpoint, self.limits["default"])
        current_count = sum(count for _, count in self.requests[user_id])

        allowed = current_count < limit
        remaining = max(0, limit - current_count)

        return allowed, remaining

    def record_request(self, user_id: str):
        """Record a request"""
        self.requests[user_id].append((time.time(), 1))

    async def enforce_rate_limit(self, user_id: str, endpoint: str = "default"):
        """
        Enforce rate limit - raise HTTPException if exceeded

        Raises:
            HTTPException: 429 if rate limit exceeded
        """
        allowed, remaining = self.check_rate_limit(user_id, endpoint)

        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Please slow down.",
                headers={"Retry-After": "60"},
            )

        self.record_request(user_id)


# Global instance
rate_limiter = RateLimiter()
