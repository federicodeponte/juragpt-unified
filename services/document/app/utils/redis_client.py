"""
ABOUTME: Redis client for ephemeral PII mapping storage
ABOUTME: Manages encrypted temporary storage of PII anonymization mappings with connection pooling
"""

import json
from typing import Dict, Optional

import redis
from redis.connection import ConnectionPool

from app.config import settings
from app.utils.logging import logger


class RedisClient:
    """
    Redis client with connection pooling for PII mapping cache

    Connection Pool Benefits:
    - Reuses connections across requests (reduces latency)
    - Limits max connections (prevents resource exhaustion)
    - Automatic connection health checks
    - Thread-safe connection management
    """

    def __init__(self):
        # Create connection pool (shared across all operations)
        self.pool = ConnectionPool(
            host=settings.redis_host,
            port=settings.redis_port,
            password=settings.redis_password if settings.redis_password else None,
            db=settings.redis_db,
            max_connections=settings.redis_max_connections,
            socket_timeout=settings.redis_socket_timeout,
            socket_connect_timeout=settings.redis_socket_connect_timeout,
            socket_keepalive=settings.redis_socket_keepalive,
            health_check_interval=settings.redis_health_check_interval,
            decode_responses=True,  # Auto-decode bytes to strings
        )

        # Create Redis client using the pool
        self.client = redis.Redis(connection_pool=self.pool)

        logger.info(
            f"Redis connection pool initialized: "
            f"max_connections={settings.redis_max_connections}, "
            f"host={settings.redis_host}:{settings.redis_port}"
        )

    def store_pii_mapping(
        self, request_id: str, mapping: Dict[str, str], ttl: Optional[int] = None
    ) -> bool:
        """
        Store PII mapping with TTL
        Args:
            request_id: Unique request identifier
            mapping: Dictionary of {placeholder: original_value}
            ttl: Time-to-live in seconds (default from settings)
        Returns:
            True if stored successfully
        """
        ttl = ttl or settings.pii_mapping_ttl
        key = f"pii:{request_id}"

        try:
            # Store as JSON with TTL
            self.client.setex(key, ttl, json.dumps(mapping, ensure_ascii=False))
            return True
        except redis.RedisError as e:
            print(f"Error storing PII mapping: {e}")
            return False

    def get_pii_mapping(self, request_id: str) -> Optional[Dict[str, str]]:
        """
        Retrieve PII mapping by request ID
        Returns None if not found or expired
        """
        key = f"pii:{request_id}"

        try:
            data = self.client.get(key)
            if data:
                return json.loads(data)
            return None
        except (redis.RedisError, json.JSONDecodeError) as e:
            print(f"Error retrieving PII mapping: {e}")
            return None

    def delete_pii_mapping(self, request_id: str) -> bool:
        """
        Delete PII mapping immediately (after de-anonymization)
        """
        key = f"pii:{request_id}"

        try:
            self.client.delete(key)
            return True
        except redis.RedisError as e:
            print(f"Error deleting PII mapping: {e}")
            return False

    def mapping_exists(self, request_id: str) -> bool:
        """Check if mapping exists for request ID"""
        key = f"pii:{request_id}"
        try:
            return self.client.exists(key) > 0
        except redis.RedisError:
            return False

    def get_ttl(self, request_id: str) -> int:
        """Get remaining TTL for a mapping (in seconds)"""
        key = f"pii:{request_id}"
        try:
            ttl = self.client.ttl(key)
            return ttl if ttl > 0 else 0
        except redis.RedisError:
            return 0

    def health_check(self) -> bool:
        """Check if Redis is accessible"""
        try:
            return self.client.ping()
        except redis.RedisError:
            return False

    def clear_all_pii_mappings(self) -> int:
        """
        Clear all PII mappings (use with caution!)
        Returns number of keys deleted
        """
        try:
            keys = self.client.keys("pii:*")
            if keys:
                return self.client.delete(*keys)
            return 0
        except redis.RedisError as e:
            logger.error(f"Error clearing PII mappings: {e}")
            return 0

    def get_pool_stats(self) -> Dict[str, int]:
        """
        Get connection pool statistics for monitoring

        Returns:
            Dictionary with pool metrics:
            - max_connections: Maximum pool size
            - in_use_connections: Currently active connections
            - available_connections: Idle connections ready for use
        """
        pool_stats = {
            "max_connections": self.pool.max_connections,
            "in_use_connections": len(self.pool._in_use_connections),
            "available_connections": len(self.pool._available_connections),
        }
        return pool_stats

    def close_pool(self) -> None:
        """
        Close all connections in the pool

        Should be called on application shutdown to cleanly close connections
        """
        try:
            self.pool.disconnect()
            logger.info("Redis connection pool closed")
        except Exception as e:
            logger.error(f"Error closing Redis pool: {e}")

    # ============================================================================
    # Query Result Caching
    # ============================================================================

    def cache_query_result(
        self, cache_key: str, result: Dict, ttl: Optional[int] = None
    ) -> bool:
        """
        Cache query results (retrieval results, document lookups, etc.)

        Args:
            cache_key: Unique key for the cached result (e.g., "query:doc_id:query_hash")
            result: Dictionary to cache (must be JSON-serializable)
            ttl: Time-to-live in seconds (default: 3600 = 1 hour)

        Returns:
            True if cached successfully
        """
        ttl = ttl or 3600  # Default 1 hour cache
        key = f"cache:{cache_key}"

        try:
            self.client.setex(key, ttl, json.dumps(result, ensure_ascii=False, default=str))
            return True
        except (redis.RedisError, TypeError) as e:
            logger.error(f"Error caching query result: {e}")
            return False

    def get_cached_result(self, cache_key: str) -> Optional[Dict]:
        """
        Retrieve cached query result

        Args:
            cache_key: Unique key for the cached result

        Returns:
            Cached dictionary or None if not found/expired
        """
        key = f"cache:{cache_key}"

        try:
            data = self.client.get(key)
            if data:
                return json.loads(data)
            return None
        except (redis.RedisError, json.JSONDecodeError) as e:
            logger.error(f"Error retrieving cached result: {e}")
            return None

    def invalidate_cache(self, pattern: str) -> int:
        """
        Invalidate cache entries matching pattern

        Args:
            pattern: Redis key pattern (e.g., "cache:doc:123abc*")

        Returns:
            Number of keys deleted
        """
        try:
            keys = self.client.keys(f"cache:{pattern}")
            if keys:
                return self.client.delete(*keys)
            return 0
        except redis.RedisError as e:
            logger.error(f"Error invalidating cache: {e}")
            return 0

    def cache_exists(self, cache_key: str) -> bool:
        """Check if cache entry exists"""
        key = f"cache:{cache_key}"
        try:
            return self.client.exists(key) > 0
        except redis.RedisError:
            return False

    def get_cache_ttl(self, cache_key: str) -> int:
        """Get remaining TTL for a cache entry (in seconds)"""
        key = f"cache:{cache_key}"
        try:
            ttl = self.client.ttl(key)
            return ttl if ttl > 0 else 0
        except redis.RedisError:
            return 0


# Global instance
redis_client = RedisClient()
