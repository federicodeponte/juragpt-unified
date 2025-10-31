"""
ABOUTME: Authentication models for Supabase Auth integration
ABOUTME: Simple JWT-based auth with per-user permissions
"""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr


class User(BaseModel):
    """User model from Supabase Auth"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    created_at: datetime
    updated_at: Optional[datetime] = None


class UserUsage(BaseModel):
    """User usage tracking for quotas"""

    user_id: uuid.UUID
    month: str  # YYYY-MM format
    tokens_used: int = 0
    queries_count: int = 0
    documents_indexed: int = 0

    # Quotas (configured per plan)
    token_quota: int = 100000  # 100k tokens/month
    query_quota: int = 1000
    document_quota: int = 100


class TokenClaims(BaseModel):
    """JWT token claims"""

    sub: str  # User ID
    email: str
    exp: int  # Expiration timestamp
    iat: int  # Issued at
