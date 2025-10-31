"""
ABOUTME: Security headers middleware for production hardening
ABOUTME: Implements OWASP recommended security headers
"""

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.config import settings


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add security headers to all responses

    Implements OWASP recommended headers:
    - HSTS (HTTP Strict Transport Security)
    - X-Content-Type-Options (prevent MIME sniffing)
    - X-Frame-Options (prevent clickjacking)
    - X-XSS-Protection (XSS filter)
    - Content-Security-Policy (CSP)
    - Referrer-Policy (control referrer information)
    - Permissions-Policy (control browser features)
    """

    async def dispatch(self, request: Request, call_next):
        """Add security headers to response"""
        response: Response = await call_next(request)

        # HSTS - Force HTTPS (only in production)
        if settings.environment == "production":
            # max-age=31536000 (1 year), includeSubDomains, preload
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )

        # X-Content-Type-Options - Prevent MIME sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # X-Frame-Options - Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"

        # X-XSS-Protection - Enable XSS filter (legacy browsers)
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Content-Security-Policy - Strict CSP for API
        # API-only server, no inline scripts/styles allowed
        csp_directives = [
            "default-src 'none'",  # Deny all by default
            "frame-ancestors 'none'",  # No framing (redundant with X-Frame-Options)
            "base-uri 'self'",  # Restrict base tag
            "form-action 'self'",  # Restrict form submissions
        ]
        response.headers["Content-Security-Policy"] = "; ".join(csp_directives)

        # Referrer-Policy - Control referrer information leakage
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Permissions-Policy - Disable unnecessary browser features
        # API server doesn't need geolocation, camera, microphone, etc.
        permissions_directives = [
            "geolocation=()",
            "camera=()",
            "microphone=()",
            "payment=()",
            "usb=()",
            "magnetometer=()",
            "gyroscope=()",
            "accelerometer=()",
        ]
        response.headers["Permissions-Policy"] = ", ".join(permissions_directives)

        # X-Permitted-Cross-Domain-Policies - Restrict Adobe Flash/PDF
        response.headers["X-Permitted-Cross-Domain-Policies"] = "none"

        # Cache-Control - Prevent caching of sensitive API responses
        # Allow caching only for static endpoints like /health, /metrics
        if request.url.path not in ["/api/v1/health", "/api/v1/metrics", "/"]:
            response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
            response.headers["Pragma"] = "no-cache"

        return response
