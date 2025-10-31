"""
Tests for Redis caching functionality
Phase 15: Query result caching
"""

import pytest
from unittest.mock import Mock, patch
from app.utils.redis_client import RedisClient


class TestQueryResultCaching:
    """Test query result caching functionality"""

    @pytest.fixture
    def redis_client(self):
        """Create Redis client for testing"""
        with patch("app.utils.redis_client.redis.Redis"):
            client = RedisClient()
            client.client = Mock()
            return client

    def test_cache_query_result(self, redis_client):
        """Test caching query results"""
        cache_key = "query:doc123:hash456:5:0.7"
        result = {
            "results": [
                {"chunk_id": "123", "content": "test", "similarity": 0.9}
            ],
            "metadata": {"document_id": "doc123"}
        }

        redis_client.cache_query_result(cache_key, result, ttl=3600)

        # Verify setex was called with correct parameters
        redis_client.client.setex.assert_called_once()
        args = redis_client.client.setex.call_args[0]
        assert args[0] == f"cache:{cache_key}"
        assert args[1] == 3600

    def test_get_cached_result_hit(self, redis_client):
        """Test retrieving cached result - cache hit"""
        cache_key = "query:doc123:hash456:5:0.7"
        cached_data = '{"results": [{"chunk_id": "123"}]}'

        redis_client.client.get.return_value = cached_data

        result = redis_client.get_cached_result(cache_key)

        assert result is not None
        assert result["results"][0]["chunk_id"] == "123"
        redis_client.client.get.assert_called_once_with(f"cache:{cache_key}")

    def test_get_cached_result_miss(self, redis_client):
        """Test retrieving cached result - cache miss"""
        cache_key = "query:doc123:hash456:5:0.7"

        redis_client.client.get.return_value = None

        result = redis_client.get_cached_result(cache_key)

        assert result is None

    def test_invalidate_cache_pattern(self, redis_client):
        """Test cache invalidation by pattern"""
        pattern = "query:doc123:*"

        redis_client.client.keys.return_value = [
            "cache:query:doc123:abc",
            "cache:query:doc123:def"
        ]
        redis_client.client.delete.return_value = 2

        deleted = redis_client.invalidate_cache(pattern)

        assert deleted == 2
        redis_client.client.keys.assert_called_once_with(f"cache:{pattern}")
        redis_client.client.delete.assert_called_once()

    def test_cache_exists(self, redis_client):
        """Test checking if cache entry exists"""
        cache_key = "query:doc123:hash456"

        redis_client.client.exists.return_value = 1

        exists = redis_client.cache_exists(cache_key)

        assert exists is True
        redis_client.client.exists.assert_called_once_with(f"cache:{cache_key}")

    def test_cache_not_exists(self, redis_client):
        """Test checking if cache entry does not exist"""
        cache_key = "query:doc123:hash456"

        redis_client.client.exists.return_value = 0

        exists = redis_client.cache_exists(cache_key)

        assert exists is False

    def test_get_cache_ttl(self, redis_client):
        """Test getting remaining TTL for cache entry"""
        cache_key = "query:doc123:hash456"

        redis_client.client.ttl.return_value = 1800

        ttl = redis_client.get_cache_ttl(cache_key)

        assert ttl == 1800
        redis_client.client.ttl.assert_called_once_with(f"cache:{cache_key}")

    def test_cache_error_handling(self, redis_client):
        """Test cache error handling"""
        import redis as redis_module

        cache_key = "query:doc123:hash456"

        redis_client.client.get.side_effect = redis_module.RedisError("Connection error")

        result = redis_client.get_cached_result(cache_key)

        assert result is None  # Should return None on error, not raise
