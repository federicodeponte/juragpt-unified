"""
ABOUTME: Auth middleware using Supabase JWT validation
ABOUTME: Simple dependency injection for FastAPI routes
"""

import uuid
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.auth.models import User
from app.db.supabase_client import supabase_client

security = HTTPBearer()


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> User:
    """
    Validate JWT token and return current user
    Uses Supabase's built-in JWT validation
    """
    token = credentials.credentials

    try:
        # Verify JWT with Supabase
        auth_response = supabase_client.client.auth.get_user(token)

        if not auth_response or not auth_response.user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
            )

        user = auth_response.user

        return User(
            id=uuid.UUID(user.id),
            email=user.email,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Could not validate credentials: {str(e)}",
        )


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
) -> Optional[User]:
    """Optional auth for endpoints that work with/without auth"""
    if not credentials:
        return None

    try:
        return await get_current_user(credentials)
    except HTTPException:
        return None


def require_auth(user: User = Depends(get_current_user)) -> User:
    """Simple dependency for routes that require auth"""
    return user
