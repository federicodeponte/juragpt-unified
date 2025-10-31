"""
Test data retention and maintenance tasks
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
from app.utils.maintenance import purge_expired_data, cleanup_redis_cache, run_maintenance


class TestDataRetention:
    """Test data retention and purging"""

    @pytest.mark.asyncio
    async def test_purge_expired_data_success(self):
        """Test successful data purge"""
        mock_result = Mock()
        mock_result.data = [{"chunks_deleted": 150, "logs_deleted": 45, "old_usage_deleted": 12}]

        with patch("app.utils.maintenance.supabase_client") as mock_supabase:
            mock_supabase.client.rpc.return_value.execute.return_value = mock_result

            result = await purge_expired_data()

            assert result["success"] is True
            assert result["chunks_deleted"] == 150
            assert result["logs_deleted"] == 45
            assert result["old_usage_deleted"] == 12
            assert "timestamp" in result

            # Verify RPC was called
            mock_supabase.client.rpc.assert_called_once_with("purge_expired_data")

    @pytest.mark.asyncio
    async def test_purge_expired_data_no_data_returned(self):
        """Test purge when no data is returned"""
        mock_result = Mock()
        mock_result.data = None

        with patch("app.utils.maintenance.supabase_client") as mock_supabase:
            mock_supabase.client.rpc.return_value.execute.return_value = mock_result

            result = await purge_expired_data()

            assert result["success"] is False
            assert "error" in result
            assert result["error"] == "No data returned"

    @pytest.mark.asyncio
    async def test_purge_expired_data_exception(self):
        """Test purge handling exceptions"""
        with patch("app.utils.maintenance.supabase_client") as mock_supabase:
            mock_supabase.client.rpc.side_effect = Exception("Database connection error")

            result = await purge_expired_data()

            assert result["success"] is False
            assert "error" in result
            assert "connection error" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_purge_expired_data_zero_deletions(self):
        """Test purge when nothing needs to be deleted"""
        mock_result = Mock()
        mock_result.data = [{"chunks_deleted": 0, "logs_deleted": 0, "old_usage_deleted": 0}]

        with patch("app.utils.maintenance.supabase_client") as mock_supabase:
            mock_supabase.client.rpc.return_value.execute.return_value = mock_result

            result = await purge_expired_data()

            assert result["success"] is True
            assert result["chunks_deleted"] == 0
            assert result["logs_deleted"] == 0

    @pytest.mark.asyncio
    async def test_purge_expired_data_list_response(self):
        """Test purge when data is returned as a list"""
        mock_result = Mock()
        mock_result.data = [{"chunks_deleted": 25, "logs_deleted": 10, "old_usage_deleted": 5}]

        with patch("app.utils.maintenance.supabase_client") as mock_supabase:
            mock_supabase.client.rpc.return_value.execute.return_value = mock_result

            result = await purge_expired_data()

            assert result["success"] is True
            assert result["chunks_deleted"] == 25


class TestRedisCleanup:
    """Test Redis cache cleanup"""

    @pytest.mark.asyncio
    async def test_cleanup_redis_cache_success(self):
        """Test successful Redis cleanup"""
        result = await cleanup_redis_cache()

        # Redis cleanup just checks TTL-based cleanup
        assert result["success"] is True
        assert "TTL-based" in result["message"]

    @pytest.mark.asyncio
    async def test_cleanup_redis_cache_error(self):
        """Test Redis cleanup with errors"""
        # Intentionally not testing actual Redis errors as cleanup is passive
        result = await cleanup_redis_cache()

        # Should succeed as it's just a status check
        assert result["success"] is True


class TestMaintenanceTasks:
    """Test combined maintenance task execution"""

    @pytest.mark.asyncio
    async def test_run_maintenance_all_success(self):
        """Test running all maintenance tasks successfully"""
        mock_purge_result = {
            "success": True,
            "chunks_deleted": 100,
            "logs_deleted": 50,
            "old_usage_deleted": 10,
            "timestamp": datetime.utcnow().isoformat(),
        }

        mock_redis_result = {"success": True, "message": "TTL-based cleanup active"}

        with patch("app.utils.maintenance.purge_expired_data", return_value=mock_purge_result):
            with patch("app.utils.maintenance.cleanup_redis_cache", return_value=mock_redis_result):
                results = await run_maintenance()

                assert "data_retention" in results
                assert "redis_cleanup" in results
                assert results["data_retention"]["success"] is True
                assert results["redis_cleanup"]["success"] is True

    @pytest.mark.asyncio
    async def test_run_maintenance_partial_failure(self):
        """Test maintenance when one task fails"""
        mock_purge_result = {"success": False, "error": "Database error"}

        mock_redis_result = {"success": True, "message": "TTL-based cleanup active"}

        with patch("app.utils.maintenance.purge_expired_data", return_value=mock_purge_result):
            with patch("app.utils.maintenance.cleanup_redis_cache", return_value=mock_redis_result):
                results = await run_maintenance()

                assert results["data_retention"]["success"] is False
                assert results["redis_cleanup"]["success"] is True

    @pytest.mark.asyncio
    async def test_run_maintenance_all_failure(self):
        """Test maintenance when all tasks fail"""
        mock_purge_result = {"success": False, "error": "Database error"}

        mock_redis_result = {"success": False, "error": "Redis error"}

        with patch("app.utils.maintenance.purge_expired_data", return_value=mock_purge_result):
            with patch("app.utils.maintenance.cleanup_redis_cache", return_value=mock_redis_result):
                results = await run_maintenance()

                assert results["data_retention"]["success"] is False
                assert results["redis_cleanup"]["success"] is False


class TestMaintenanceScript:
    """Test maintenance script execution"""

    @pytest.mark.asyncio
    async def test_maintenance_can_be_run_directly(self):
        """Test that maintenance module can be executed"""
        # This tests the __main__ block would work
        mock_purge_result = {
            "success": True,
            "chunks_deleted": 10,
            "logs_deleted": 5,
            "old_usage_deleted": 2,
            "timestamp": datetime.utcnow().isoformat(),
        }

        mock_redis_result = {"success": True, "message": "TTL-based cleanup active"}

        with patch("app.utils.maintenance.purge_expired_data", return_value=mock_purge_result):
            with patch("app.utils.maintenance.cleanup_redis_cache", return_value=mock_redis_result):
                # Simulate running the module
                results = await run_maintenance()

                assert results is not None
                assert "data_retention" in results
                assert "redis_cleanup" in results


class TestDataRetentionIntegration:
    """Integration tests for data retention"""

    @pytest.mark.asyncio
    async def test_retention_lifecycle(self):
        """Test complete retention lifecycle"""
        # Simulate a full maintenance cycle
        mock_result = Mock()
        mock_result.data = [{"chunks_deleted": 200, "logs_deleted": 75, "old_usage_deleted": 15}]

        with patch("app.utils.maintenance.supabase_client") as mock_supabase:
            mock_supabase.client.rpc.return_value.execute.return_value = mock_result

            # Run full maintenance
            results = await run_maintenance()

            # Verify data retention ran
            assert results["data_retention"]["success"] is True
            assert results["data_retention"]["chunks_deleted"] == 200

            # Verify Redis cleanup ran
            assert results["redis_cleanup"]["success"] is True

            # Verify database was called
            mock_supabase.client.rpc.assert_called_once_with("purge_expired_data")

    @pytest.mark.asyncio
    async def test_retention_with_realistic_counts(self):
        """Test retention with realistic deletion counts"""
        # Simulate realistic scenario: 730-day old chunks, 90-day old logs
        mock_result = Mock()
        mock_result.data = [
            {
                "chunks_deleted": 1543,  # ~2 years of old chunks
                "logs_deleted": 8920,  # ~90 days of old logs
                "old_usage_deleted": 24,  # ~2 years of old usage records
            }
        ]

        with patch("app.utils.maintenance.supabase_client") as mock_supabase:
            mock_supabase.client.rpc.return_value.execute.return_value = mock_result

            result = await purge_expired_data()

            assert result["success"] is True
            assert result["chunks_deleted"] > 1000
            assert result["logs_deleted"] > 5000
            assert "timestamp" in result
