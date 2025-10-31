"""
ABOUTME: Authentication endpoints for login and API key management
ABOUTME: Provides JWT token generation and API key CRUD operations
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from auditor.config.settings import get_settings
from auditor.security import (
    TokenData,
    create_access_token,
    get_current_user,
    hash_password,
    register_api_key,
    require_auth,
    verify_password,
)

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/auth", tags=["authentication"])


# Request/Response Models
class LoginRequest(BaseModel):
    """Login request with username and password"""
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8, max_length=100)


class TokenResponse(BaseModel):
    """JWT token response"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # Seconds until expiration


class RefreshRequest(BaseModel):
    """Token refresh request"""
    refresh_token: str


class CreateAPIKeyRequest(BaseModel):
    """Request to create a new API key"""
    name: str = Field(..., min_length=1, max_length=100, description="Friendly name for the API key")
    scopes: List[str] = Field(default=["verify"], description="List of permission scopes")
    rate_limit: Optional[int] = Field(None, ge=1, le=10000, description="Custom rate limit (req/min)")
    expires_in_days: Optional[int] = Field(None, ge=1, le=365, description="Days until expiration")


class APIKeyResponse(BaseModel):
    """API key creation response"""
    api_key: str = Field(..., description="The API key (shown only once)")
    key_id: str
    user_id: str
    scopes: List[str]
    rate_limit: int
    created_at: datetime
    expires_at: Optional[datetime]


class APIKeyInfo(BaseModel):
    """API key information (without the actual key)"""
    key_id: str
    name: str
    user_id: str
    scopes: List[str]
    rate_limit: int
    created_at: datetime
    expires_at: Optional[datetime]
    last_used: Optional[datetime] = None


# In-memory user store (replace with database in production)
_users: Dict[str, Dict] = {
    "admin": {
        "username": "admin",
        "password_hash": hash_password("admin123"),  # Change in production!
        "scopes": ["admin", "verify"]
    },
    "demo": {
        "username": "demo",
        "password_hash": hash_password("demo123"),
        "scopes": ["verify"]
    }
}


def authenticate_user(username: str, password: str) -> Optional[Dict]:
    """
    Authenticate a user with username and password.

    Args:
        username: Username to authenticate
        password: Password to verify

    Returns:
        User dict if authenticated, None otherwise
    """
    user = _users.get(username)
    if not user:
        return None

    if not verify_password(password, user["password_hash"]):
        return None

    return user


@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest) -> TokenResponse:
    """
    Login with username and password to get a JWT token.

    **Example**:
    ```bash
    curl -X POST http://localhost:8000/auth/login \\
      -H "Content-Type: application/json" \\
      -d '{"username": "admin", "password": "admin123"}'
    ```

    **Response**:
    ```json
    {
      "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
      "token_type": "bearer",
      "expires_in": 1800
    }
    ```
    """
    settings = get_settings()

    # Authenticate user
    user = authenticate_user(request.username, request.password)
    if not user:
        logger.warning(f"Failed login attempt for user: {request.username}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create access token
    token_data = {
        "sub": user["username"],
        "scopes": user["scopes"]
    }
    access_token = create_access_token(token_data)

    logger.info(f"User logged in: {user['username']}")

    return TokenResponse(
        access_token=access_token,
        expires_in=settings.jwt_access_token_expire_minutes * 60
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: RefreshRequest,
    current_user: TokenData = Depends(require_auth)
) -> TokenResponse:
    """
    Refresh an existing JWT token.

    **Note**: Currently returns a new token with the same claims.
    In production, implement proper refresh token rotation.
    """
    settings = get_settings()

    # Create new access token with existing claims
    token_data = {
        "sub": current_user.sub,
        "scopes": current_user.scopes
    }
    access_token = create_access_token(token_data)

    logger.info(f"Token refreshed for user: {current_user.sub}")

    return TokenResponse(
        access_token=access_token,
        expires_in=settings.jwt_access_token_expire_minutes * 60
    )


@router.post("/api-keys", response_model=APIKeyResponse)
async def create_api_key(
    request: CreateAPIKeyRequest,
    current_user: TokenData = Depends(require_auth)
) -> APIKeyResponse:
    """
    Create a new API key for programmatic access.

    **Requires Authentication**: JWT token with 'admin' or 'verify' scope

    **Example**:
    ```bash
    curl -X POST http://localhost:8000/auth/api-keys \\
      -H "Authorization: Bearer <your-jwt-token>" \\
      -H "Content-Type: application/json" \\
      -d '{
        "name": "my-app",
        "scopes": ["verify"],
        "rate_limit": 100,
        "expires_in_days": 90
      }'
    ```

    **Response**:
    ```json
    {
      "api_key": "ak_dGVzdF9rZXlfMTIzNDU2Nzg5MA",
      "key_id": "my-app-1234",
      "user_id": "admin",
      "scopes": ["verify"],
      "rate_limit": 100,
      "created_at": "2025-10-30T10:00:00Z",
      "expires_at": "2026-01-28T10:00:00Z"
    }
    ```

    ⚠️ **Important**: Save the `api_key` value - it's only shown once!
    """
    settings = get_settings()

    # Calculate expiration
    expires_at = None
    if request.expires_in_days:
        expires_at = datetime.utcnow() + timedelta(days=request.expires_in_days)

    # Determine rate limit
    rate_limit = request.rate_limit or settings.rate_limit_per_minute

    # Generate unique key ID
    import uuid
    key_id = f"{request.name}-{uuid.uuid4().hex[:8]}"

    # Register API key
    api_key = register_api_key(
        key_id=key_id,
        user_id=current_user.sub,
        scopes=request.scopes,
        rate_limit=rate_limit,
        expires_at=expires_at
    )

    logger.info(
        f"API key created: {key_id} for user {current_user.sub} "
        f"(rate_limit={rate_limit}, expires={expires_at})"
    )

    return APIKeyResponse(
        api_key=api_key,
        key_id=key_id,
        user_id=current_user.sub,
        scopes=request.scopes,
        rate_limit=rate_limit,
        created_at=datetime.utcnow(),
        expires_at=expires_at
    )


@router.get("/api-keys", response_model=List[APIKeyInfo])
async def list_api_keys(
    current_user: TokenData = Depends(require_auth)
) -> List[APIKeyInfo]:
    """
    List all API keys for the current user.

    **Requires Authentication**: JWT token

    **Example**:
    ```bash
    curl http://localhost:8000/auth/api-keys \\
      -H "Authorization: Bearer <your-jwt-token>"
    ```
    """
    # This would query the database in production
    # For now, return empty list as keys are in-memory
    logger.info(f"API keys listed for user: {current_user.sub}")

    return []  # TODO: Implement database-backed key listing


@router.delete("/api-keys/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(
    key_id: str,
    current_user: TokenData = Depends(require_auth)
):
    """
    Revoke an API key.

    **Requires Authentication**: JWT token

    **Example**:
    ```bash
    curl -X DELETE http://localhost:8000/auth/api-keys/my-app-1234 \\
      -H "Authorization: Bearer <your-jwt-token>"
    ```
    """
    # This would delete from database in production
    # For now, just log
    logger.info(f"API key revoked: {key_id} by user {current_user.sub}")

    # TODO: Implement database-backed key deletion
    return None


@router.get("/me", response_model=Dict)
async def get_current_user_info(
    current_user: TokenData = Depends(require_auth)
) -> Dict:
    """
    Get information about the currently authenticated user.

    **Requires Authentication**: JWT token

    **Example**:
    ```bash
    curl http://localhost:8000/auth/me \\
      -H "Authorization: Bearer <your-jwt-token>"
    ```

    **Response**:
    ```json
    {
      "user_id": "admin",
      "scopes": ["admin", "verify"],
      "token_expires_at": "2025-10-30T10:30:00Z"
    }
    ```
    """
    return {
        "user_id": current_user.sub,
        "scopes": current_user.scopes,
        "token_expires_at": current_user.exp.isoformat()
    }
