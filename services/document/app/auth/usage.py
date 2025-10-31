"""
ABOUTME: User usage tracking and quota enforcement
ABOUTME: Simple, database-backed quota management
"""

import uuid
from datetime import datetime

from fastapi import HTTPException, status

from app.auth.models import UserUsage
from app.db.supabase_client import supabase_client
from app.utils.logging import logger


class UsageTracker:
    """Track and enforce user quotas"""

    @staticmethod
    async def check_quota(user_id: uuid.UUID, quota_type: str, amount: int = 1) -> bool:
        """
        Check if user is within quota

        Args:
            user_id: User UUID
            quota_type: 'tokens', 'queries', or 'documents'
            amount: Amount to check against quota

        Returns:
            True if within quota, False otherwise
        """
        try:
            result = supabase_client.client.rpc(
                "check_user_quota",
                {"p_user_id": str(user_id), "p_quota_type": quota_type, "p_amount": amount},
            ).execute()

            return result.data if result.data is not None else False

        except Exception as e:
            logger.error(f"Quota check failed: {str(e)}")
            # Fail open in case of errors (don't block users)
            return True

    @staticmethod
    async def increment_usage(
        user_id: uuid.UUID, tokens: int = 0, queries: int = 0, documents: int = 0
    ):
        """Increment user usage counters"""
        try:
            supabase_client.client.rpc(
                "increment_user_usage",
                {
                    "p_user_id": str(user_id),
                    "p_tokens": tokens,
                    "p_queries": queries,
                    "p_documents": documents,
                },
            ).execute()

        except Exception as e:
            logger.error(f"Usage increment failed: {str(e)}")
            # Non-critical, don't block the request

    @staticmethod
    async def get_usage(user_id: uuid.UUID) -> UserUsage:
        """Get current month usage for user"""
        current_month = datetime.now().strftime("%Y-%m")

        try:
            result = (
                supabase_client.client.table("user_usage")
                .select("*")
                .eq("user_id", str(user_id))
                .eq("month", current_month)
                .execute()
            )

            if result.data:
                return UserUsage(**result.data[0])
            else:
                # Return default quota if no record exists
                return UserUsage(user_id=user_id, month=current_month)

        except Exception as e:
            logger.error(f"Usage fetch failed: {str(e)}")
            return UserUsage(user_id=user_id, month=current_month)

    @staticmethod
    async def enforce_quota(user_id: uuid.UUID, quota_type: str, amount: int = 1):
        """
        Enforce quota - raise HTTPException if exceeded

        Raises:
            HTTPException: 429 if quota exceeded
        """
        within_quota = await UsageTracker.check_quota(user_id, quota_type, amount)

        if not within_quota:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Quota exceeded for {quota_type}. Please upgrade your plan.",
            )


# Global instance
usage_tracker = UsageTracker()
