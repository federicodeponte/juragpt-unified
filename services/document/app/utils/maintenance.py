"""
ABOUTME: Maintenance utilities for data retention and cleanup
ABOUTME: Scheduled tasks for GDPR compliance and database hygiene
"""

import asyncio
from datetime import datetime

from app.db.supabase_client import supabase_client
from app.utils.logging import logger


async def purge_expired_data() -> dict:
    """
    Purge expired data according to retention policies

    Should be run daily via cron job
    Example: 0 2 * * * cd /app && python -m app.utils.maintenance

    Returns:
        dict with counts of deleted records
    """
    try:
        logger.info("Starting data retention purge...")

        result = supabase_client.client.rpc("purge_expired_data").execute()

        if result.data:
            data = result.data[0] if isinstance(result.data, list) else result.data
            chunks_deleted = data.get("chunks_deleted", 0)
            logs_deleted = data.get("logs_deleted", 0)
            old_usage_deleted = data.get("old_usage_deleted", 0)

            logger.info(
                f"Data retention purge completed: "
                f"chunks={chunks_deleted}, "
                f"logs={logs_deleted}, "
                f"old_usage={old_usage_deleted}"
            )

            return {
                "success": True,
                "chunks_deleted": chunks_deleted,
                "logs_deleted": logs_deleted,
                "old_usage_deleted": old_usage_deleted,
                "timestamp": datetime.utcnow().isoformat(),
            }
        else:
            logger.warning("No data returned from purge function")
            return {"success": False, "error": "No data returned"}

    except Exception as e:
        logger.error(f"Data retention purge failed: {str(e)}")
        return {"success": False, "error": str(e)}


async def cleanup_redis_cache():
    """Clean up orphaned PII mappings in Redis"""

    try:
        # Redis handles TTL automatically, but we can do manual cleanup if needed
        logger.info("Redis cache cleanup (automatic via TTL)")
        return {"success": True, "message": "TTL-based cleanup active"}
    except Exception as e:
        logger.error(f"Redis cleanup error: {str(e)}")
        return {"success": False, "error": str(e)}


async def run_maintenance():
    """Run all maintenance tasks"""
    logger.info("=== Starting maintenance tasks ===")

    results = {
        "data_retention": await purge_expired_data(),
        "redis_cleanup": await cleanup_redis_cache(),
    }

    logger.info("=== Maintenance tasks completed ===")
    return results


if __name__ == "__main__":
    # Can be run directly or via cron
    # Example cron: 0 2 * * * cd /app && python -m app.utils.maintenance
    asyncio.run(run_maintenance())
