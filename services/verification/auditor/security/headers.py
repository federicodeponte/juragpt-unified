"""
ABOUTME: Security headers middleware for API protection
ABOUTME: Adds standard security headers (CSP, HSTS, X-Frame-Options, etc.)
"""

import logging
from typing import Dict

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from auditor.config.settings import get_settings

logger = logging.getLogger(__name__)


def get_security_headers() -> Dict[str, str]:
    """
    Get standard security headers.

    Returns:
        Dict of security headers to add to all responses
    """
    settings = get_settings()

    headers = {
        # Prevent clickjacking attacks
        "X-Frame-Options": "DENY",

        # Prevent MIME type sniffing
        "X-Content-Type-Options": "nosniff",

        # Enable XSS protection in older browsers
        "X-XSS-Protection": "1; mode=block",

        # Referrer policy - don't leak information
        "Referrer-Policy": "strict-origin-when-cross-origin",

        # Permissions policy - restrict browser features
        "Permissions-Policy": (
            "accelerometer=(), "
            "camera=(), "
            "geolocation=(), "
            "gyroscope=(), "
            "magnetometer=(), "
            "microphone=(), "
            "payment=(), "
            "usb=()"
        ),

        # Content Security Policy
        "Content-Security-Policy": (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self'; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
        ),
    }

    # Add HSTS in production (requires HTTPS)
    if settings.environment == "production":
        headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains; preload"
        )

    return headers


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for adding security headers.

    Adds standard security headers to all HTTP responses.
    """

    def __init__(self, app, custom_headers: Dict[str, str] = None):
        """
        Initialize middleware.

        Args:
            app: FastAPI app instance
            custom_headers: Optional custom headers to add
        """
        super().__init__(app)
        self.security_headers = get_security_headers()

        if custom_headers:
            self.security_headers.update(custom_headers)

        logger.info(
            f"Security headers middleware initialized with "
            f"{len(self.security_headers)} headers"
        )

    async def dispatch(self, request: Request, call_next):
        """Add security headers to response"""
        response = await call_next(request)

        # Add all security headers
        for header, value in self.security_headers.items():
            response.headers[header] = value

        return response


class CORSConfig:
    """
    CORS configuration for API.

    Provides flexible CORS settings for different environments.
    """

    @staticmethod
    def get_cors_config() -> Dict[str, any]:
        """
        Get CORS configuration based on environment.

        Returns:
            Dict of CORS settings for FastAPI CORSMiddleware
        """
        settings = get_settings()

        # Development: Allow all origins
        if settings.environment == "development":
            return {
                "allow_origins": ["*"],
                "allow_credentials": True,
                "allow_methods": ["*"],
                "allow_headers": ["*"],
                "expose_headers": [
                    "X-RateLimit-Limit",
                    "X-RateLimit-Remaining",
                    "X-RateLimit-Reset"
                ]
            }

        # Production: Restricted origins
        allowed_origins = []
        if settings.cors_origins:
            allowed_origins = [
                origin.strip()
                for origin in settings.cors_origins.split(",")
            ]

        return {
            "allow_origins": allowed_origins or ["https://example.com"],
            "allow_credentials": settings.cors_allow_credentials,
            "allow_methods": settings.cors_methods.split(",") if settings.cors_methods else ["GET", "POST"],
            "allow_headers": settings.cors_headers.split(",") if settings.cors_headers else ["Content-Type", "Authorization", "X-API-Key"],
            "expose_headers": [
                "X-RateLimit-Limit",
                "X-RateLimit-Remaining",
                "X-RateLimit-Reset"
            ]
        }
