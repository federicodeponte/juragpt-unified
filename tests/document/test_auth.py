"""
Test authentication, authorization, quotas, and rate limiting
"""

import pytest
import uuid
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from fastapi import HTTPException
from app.auth.models import User, UserUsage, TokenClaims
from app.auth.middleware import get_current_user, require_auth
from app.auth.usage import UsageTracker
from app.auth.rate_limit import RateLimiter


class TestAuthModels:
    """Test authentication data models"""

    def test_user_model_creation(self):
        """Test User model"""
        user = User(id=uuid.uuid4(), email="test@example.com", created_at=datetime.utcnow())
        assert user.email == "test@example.com"
        assert isinstance(user.id, uuid.UUID)

    def test_user_usage_defaults(self):
        """Test UserUsage model with defaults"""
        usage = UserUsage(user_id=uuid.uuid4(), month="2025-01")
        assert usage.tokens_used == 0
        assert usage.queries_count == 0
        assert usage.documents_indexed == 0
        assert usage.token_quota == 100000
        assert usage.query_quota == 1000
        assert usage.document_quota == 100


class TestAuthMiddleware:
    """Test JWT validation and auth middleware"""

    @pytest.mark.asyncio
    async def test_get_current_user_valid_token(self):
        """Test JWT validation with valid token"""
        mock_credentials = Mock()
        mock_credentials.credentials = "valid-jwt-token"

        test_id = str(uuid.uuid4())
        mock_auth_response = Mock()
        mock_auth_response.user = Mock()
        mock_auth_response.user.id = test_id
        mock_auth_response.user.email = "test@example.com"
        mock_auth_response.user.created_at = datetime.utcnow().isoformat()
        mock_auth_response.user.updated_at = None

        with patch("app.auth.middleware.supabase_client") as mock_supabase:
            mock_supabase.client.auth.get_user.return_value = mock_auth_response

            user = await get_current_user(mock_credentials)

            assert user.email == "test@example.com"
            assert isinstance(user.id, uuid.UUID)
            assert str(user.id) == test_id
            mock_supabase.client.auth.get_user.assert_called_once_with("valid-jwt-token")

    @pytest.mark.asyncio
    async def test_get_current_user_invalid_token(self):
        """Test JWT validation with invalid token"""
        mock_credentials = Mock()
        mock_credentials.credentials = "invalid-token"

        with patch("app.auth.middleware.supabase_client") as mock_supabase:
            mock_supabase.client.auth.get_user.side_effect = Exception("Invalid token")

            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(mock_credentials)

            assert exc_info.value.status_code == 401
            assert "could not validate credentials" in exc_info.value.detail.lower()


class TestUsageTracking:
    """Test quota tracking and enforcement"""

    @pytest.mark.asyncio
    async def test_check_quota_within_limit(self):
        """Test quota check when within limits"""
        user_id = uuid.uuid4()

        mock_result = Mock()
        mock_result.data = True

        with patch("app.auth.usage.supabase_client") as mock_supabase:
            mock_supabase.client.rpc.return_value.execute.return_value = mock_result

            within_quota = await UsageTracker.check_quota(user_id, "tokens", 1000)

            assert within_quota is True
            mock_supabase.client.rpc.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_quota_exceeds_limit(self):
        """Test quota check when limit exceeded"""
        user_id = uuid.uuid4()

        mock_result = Mock()
        mock_result.data = False

        with patch("app.auth.usage.supabase_client") as mock_supabase:
            mock_supabase.client.rpc.return_value.execute.return_value = mock_result

            within_quota = await UsageTracker.check_quota(user_id, "tokens", 200000)

            assert within_quota is False

    @pytest.mark.asyncio
    async def test_enforce_quota_passes(self):
        """Test quota enforcement when within limits"""
        user_id = uuid.uuid4()

        with patch.object(UsageTracker, "check_quota", return_value=True):
            # Should not raise exception
            await UsageTracker.enforce_quota(user_id, "queries", 1)

    @pytest.mark.asyncio
    async def test_enforce_quota_fails(self):
        """Test quota enforcement when limit exceeded"""
        user_id = uuid.uuid4()

        with patch.object(UsageTracker, "check_quota", return_value=False):
            with pytest.raises(HTTPException) as exc_info:
                await UsageTracker.enforce_quota(user_id, "queries", 1)

            assert exc_info.value.status_code == 429
            assert "quota exceeded" in exc_info.value.detail.lower()

    @pytest.mark.asyncio
    async def test_increment_usage(self):
        """Test usage increment"""
        user_id = uuid.uuid4()

        mock_result = Mock()

        with patch("app.auth.usage.supabase_client") as mock_supabase:
            mock_supabase.client.rpc.return_value.execute.return_value = mock_result

            await UsageTracker.increment_usage(user_id, tokens=500, queries=1, documents=0)

            mock_supabase.client.rpc.assert_called_once_with(
                "increment_user_usage",
                {"p_user_id": str(user_id), "p_tokens": 500, "p_queries": 1, "p_documents": 0},
            )

    @pytest.mark.asyncio
    async def test_get_usage(self):
        """Test fetching current usage"""
        user_id = uuid.uuid4()
        current_month = datetime.now().strftime("%Y-%m")

        mock_result = Mock()
        mock_result.data = [
            {
                "user_id": str(user_id),
                "month": current_month,
                "tokens_used": 5000,
                "queries_count": 10,
                "documents_indexed": 2,
                "token_quota": 100000,
                "query_quota": 1000,
                "document_quota": 100,
            }
        ]

        with patch("app.auth.usage.supabase_client") as mock_supabase:
            mock_supabase.client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value = (
                mock_result
            )

            usage = await UsageTracker.get_usage(user_id)

            assert usage.tokens_used == 5000
            assert usage.queries_count == 10
            assert usage.documents_indexed == 2


class TestRateLimiting:
    """Test rate limiting logic"""

    def test_rate_limiter_initialization(self):
        """Test rate limiter setup"""
        limiter = RateLimiter()

        assert limiter.limits["index"] == 10
        assert limiter.limits["analyze"] == 60
        assert limiter.limits["default"] == 100

    def test_check_rate_limit_within_limit(self):
        """Test rate limit check when within limit"""
        limiter = RateLimiter()
        user_id = "user-123"

        # First request
        allowed, remaining = limiter.check_rate_limit(user_id, "index")

        assert allowed is True
        assert remaining == 10  # No requests recorded yet

    def test_check_rate_limit_exceeds_limit(self):
        """Test rate limit when exceeded"""
        limiter = RateLimiter()
        user_id = "user-456"

        # Simulate 10 requests (index limit)
        for i in range(10):
            limiter.record_request(user_id)

        allowed, remaining = limiter.check_rate_limit(user_id, "index")

        assert allowed is False
        assert remaining == 0

    @pytest.mark.asyncio
    async def test_enforce_rate_limit_passes(self):
        """Test rate limit enforcement when within limit"""
        limiter = RateLimiter()
        user_id = "user-789"

        # Should not raise exception
        await limiter.enforce_rate_limit(user_id, "analyze")

    @pytest.mark.asyncio
    async def test_enforce_rate_limit_fails(self):
        """Test rate limit enforcement when exceeded"""
        limiter = RateLimiter()
        user_id = "user-abc"

        # Fill up the rate limit
        for i in range(60):
            limiter.record_request(user_id)

        with pytest.raises(HTTPException) as exc_info:
            await limiter.enforce_rate_limit(user_id, "analyze")

        assert exc_info.value.status_code == 429
        assert "rate limit exceeded" in exc_info.value.detail.lower()
        assert exc_info.value.headers.get("Retry-After") == "60"

    def test_clean_old_requests(self):
        """Test that old requests are cleaned up"""
        import time

        limiter = RateLimiter()
        user_id = "user-cleanup"

        # Add a request
        limiter.record_request(user_id)
        assert len(limiter.requests[user_id]) == 1

        # Clean with very short window (should remove all)
        limiter._clean_old_requests(user_id, window_seconds=0)
        assert len(limiter.requests[user_id]) == 0


class TestAuthIntegration:
    """Integration tests for full auth flow"""

    @pytest.mark.asyncio
    async def test_full_auth_and_quota_flow(self):
        """Test complete auth + quota check flow"""
        user_id = uuid.uuid4()
        user = User(id=user_id, email="integration@test.com", created_at=datetime.utcnow())

        # Mock Supabase auth
        with patch("app.auth.usage.supabase_client") as mock_supabase:
            # Mock quota check - within limits
            mock_quota_result = Mock()
            mock_quota_result.data = True
            mock_supabase.client.rpc.return_value.execute.return_value = mock_quota_result

            # Check quota
            within_quota = await UsageTracker.check_quota(user_id, "queries", 1)
            assert within_quota is True

            # Increment usage
            await UsageTracker.increment_usage(user_id, queries=1)

            # Verify RPC calls
            assert mock_supabase.client.rpc.call_count == 2
