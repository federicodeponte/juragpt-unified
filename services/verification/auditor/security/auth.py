"""
ABOUTME: Authentication middleware for JWT and API key validation
ABOUTME: Provides secure authentication for API endpoints
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Optional

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

from auditor.config.settings import get_settings

logger = logging.getLogger(__name__)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Authentication schemes
bearer_scheme = HTTPBearer(auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


class TokenData(BaseModel):
    """JWT token payload data"""
    sub: str  # Subject (user ID)
    exp: datetime  # Expiration
    iat: datetime  # Issued at
    scopes: list[str] = []  # Permissions


class APIKeyData(BaseModel):
    """API key metadata"""
    key_id: str
    user_id: str
    scopes: list[str] = []
    rate_limit: int = 60  # Requests per minute
    created_at: datetime
    expires_at: Optional[datetime] = None


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash"""
    return pwd_context.verify(plain_password, hashed_password)


def hash_password(password: str) -> str:
    """Hash a password for storage"""
    return pwd_context.hash(password)


def create_access_token(data: Dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token.

    Args:
        data: Payload data to encode in the token
        expires_delta: Token expiration time (defaults to settings)

    Returns:
        Encoded JWT token
    """
    settings = get_settings()

    to_encode = data.copy()
    now = datetime.utcnow()

    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.jwt_access_token_expire_minutes)

    to_encode.update({
        "exp": expire,
        "iat": now,
    })

    encoded_jwt = jwt.encode(
        to_encode,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm
    )
    return encoded_jwt


def decode_access_token(token: str) -> TokenData:
    """
    Decode and validate a JWT access token.

    Args:
        token: JWT token to decode

    Returns:
        TokenData object with decoded payload

    Raises:
        HTTPException: If token is invalid or expired
    """
    settings = get_settings()

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm]
        )

        sub: str = payload.get("sub")
        if sub is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing subject",
                headers={"WWW-Authenticate": "Bearer"},
            )

        token_data = TokenData(
            sub=sub,
            exp=datetime.fromtimestamp(payload.get("exp")),
            iat=datetime.fromtimestamp(payload.get("iat")),
            scopes=payload.get("scopes", [])
        )

        return token_data

    except JWTError as e:
        logger.warning(f"JWT validation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme)
) -> Optional[TokenData]:
    """
    Get the current authenticated user from JWT token.

    This is an optional dependency - returns None if no auth provided.
    Use `require_auth` for endpoints that require authentication.

    Args:
        credentials: Bearer token from Authorization header

    Returns:
        TokenData if authenticated, None otherwise
    """
    if credentials is None:
        return None

    if credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication scheme",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return decode_access_token(credentials.credentials)


async def require_auth(
    user: Optional[TokenData] = Depends(get_current_user)
) -> TokenData:
    """
    Require authentication for an endpoint.

    Args:
        user: Current user from JWT token

    Returns:
        TokenData for authenticated user

    Raises:
        HTTPException: If not authenticated
    """
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


# In-memory API key store (replace with database in production)
_api_keys: Dict[str, APIKeyData] = {}


def register_api_key(
    key_id: str,
    user_id: str,
    scopes: list[str],
    rate_limit: int = 60,
    expires_at: Optional[datetime] = None
) -> str:
    """
    Register a new API key.

    Args:
        key_id: Unique identifier for the key
        user_id: User ID this key belongs to
        scopes: List of permission scopes
        rate_limit: Requests per minute limit
        expires_at: Optional expiration datetime

    Returns:
        The API key (store this securely, it's only shown once)
    """
    import secrets

    # Generate a secure random API key
    api_key = f"ak_{secrets.token_urlsafe(32)}"

    # Hash the key for storage
    key_hash = hash_password(api_key)

    _api_keys[key_hash] = APIKeyData(
        key_id=key_id,
        user_id=user_id,
        scopes=scopes,
        rate_limit=rate_limit,
        created_at=datetime.utcnow(),
        expires_at=expires_at
    )

    logger.info(f"Registered API key {key_id} for user {user_id}")
    return api_key


def verify_api_key(api_key: str) -> Optional[APIKeyData]:
    """
    Verify an API key and return its metadata.

    Args:
        api_key: API key to verify

    Returns:
        APIKeyData if valid, None otherwise
    """
    for key_hash, key_data in _api_keys.items():
        if verify_password(api_key, key_hash):
            # Check expiration
            if key_data.expires_at and datetime.utcnow() > key_data.expires_at:
                logger.warning(f"Expired API key used: {key_data.key_id}")
                return None

            return key_data

    return None


async def get_api_key_user(
    api_key: Optional[str] = Security(api_key_header)
) -> Optional[APIKeyData]:
    """
    Get the current user from API key.

    This is an optional dependency - returns None if no API key provided.

    Args:
        api_key: API key from X-API-Key header

    Returns:
        APIKeyData if valid key provided, None otherwise
    """
    if api_key is None:
        return None

    key_data = verify_api_key(api_key)
    if key_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    return key_data


async def get_current_user_flexible(
    jwt_user: Optional[TokenData] = Depends(get_current_user),
    api_key_user: Optional[APIKeyData] = Depends(get_api_key_user)
) -> Optional[Dict]:
    """
    Get current user from either JWT or API key (flexible authentication).

    Accepts both JWT tokens and API keys for authentication.

    Args:
        jwt_user: User from JWT token
        api_key_user: User from API key

    Returns:
        User info dict if authenticated, None otherwise
    """
    if jwt_user:
        return {
            "type": "jwt",
            "user_id": jwt_user.sub,
            "scopes": jwt_user.scopes
        }
    elif api_key_user:
        return {
            "type": "api_key",
            "user_id": api_key_user.user_id,
            "key_id": api_key_user.key_id,
            "scopes": api_key_user.scopes,
            "rate_limit": api_key_user.rate_limit
        }
    return None


async def require_flexible_auth(
    user: Optional[Dict] = Depends(get_current_user_flexible)
) -> Dict:
    """
    Require authentication (JWT or API key).

    Args:
        user: Current user from JWT or API key

    Returns:
        User info dict

    Raises:
        HTTPException: If not authenticated
    """
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required (provide JWT token or API key)",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user
