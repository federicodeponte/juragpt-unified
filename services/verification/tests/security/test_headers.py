"""
Tests for security headers
"""

from auditor.security import get_security_headers, CORSConfig


def test_get_security_headers():
    """Test security headers generation"""
    headers = get_security_headers()

    # Should include all standard security headers
    assert "X-Frame-Options" in headers
    assert "X-Content-Type-Options" in headers
    assert "X-XSS-Protection" in headers
    assert "Referrer-Policy" in headers
    assert "Permissions-Policy" in headers
    assert "Content-Security-Policy" in headers

    # Check specific values
    assert headers["X-Frame-Options"] == "DENY"
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["X-XSS-Protection"] == "1; mode=block"


def test_security_headers_csp():
    """Test Content Security Policy header"""
    headers = get_security_headers()
    csp = headers["Content-Security-Policy"]

    # Should include important CSP directives
    assert "default-src 'self'" in csp
    assert "script-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp


def test_security_headers_permissions_policy():
    """Test Permissions Policy header"""
    headers = get_security_headers()
    permissions = headers["Permissions-Policy"]

    # Should restrict dangerous features
    assert "camera=()" in permissions
    assert "microphone=()" in permissions
    assert "geolocation=()" in permissions


def test_cors_config_development():
    """Test CORS configuration for development"""
    # This would need settings mocking to test properly
    config = CORSConfig.get_cors_config()

    assert "allow_origins" in config
    assert "allow_methods" in config
    assert "allow_headers" in config
    assert "expose_headers" in config

    # Should expose rate limit headers
    assert "X-RateLimit-Limit" in config["expose_headers"]
    assert "X-RateLimit-Remaining" in config["expose_headers"]
    assert "X-RateLimit-Reset" in config["expose_headers"]
