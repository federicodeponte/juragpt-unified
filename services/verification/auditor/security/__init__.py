"""
ABOUTME: Security module for authentication, rate limiting, and headers
ABOUTME: Provides comprehensive security features for the API
"""

from auditor.security.auth import (
    APIKeyData,
    TokenData,
    create_access_token,
    decode_access_token,
    get_api_key_user,
    get_current_user,
    get_current_user_flexible,
    hash_password,
    register_api_key,
    require_auth,
    require_flexible_auth,
    verify_api_key,
    verify_password,
)
from auditor.security.headers import (
    CORSConfig,
    SecurityHeadersMiddleware,
    get_security_headers,
)
from auditor.security.rate_limit import (
    RateLimitMiddleware,
    RateLimiter,
    get_client_id,
    get_rate_limiter,
)

__all__ = [
    # Authentication
    "TokenData",
    "APIKeyData",
    "create_access_token",
    "decode_access_token",
    "verify_password",
    "hash_password",
    "get_current_user",
    "require_auth",
    "get_api_key_user",
    "register_api_key",
    "verify_api_key",
    "get_current_user_flexible",
    "require_flexible_auth",
    # Rate limiting
    "RateLimiter",
    "RateLimitMiddleware",
    "get_rate_limiter",
    "get_client_id",
    # Security headers
    "SecurityHeadersMiddleware",
    "CORSConfig",
    "get_security_headers",
]
