"""
Tests for authentication functionality (JWT and API keys)
"""

import pytest
from datetime import datetime, timedelta
from jose import jwt

from auditor.security import (
    create_access_token,
    decode_access_token,
    verify_password,
    hash_password,
    register_api_key,
    verify_api_key,
)
from auditor.config.settings import get_settings


def test_password_hashing():
    """Test password hashing and verification"""
    password = "test_password_123"
    hashed = hash_password(password)

    # Hash should be different from password
    assert hashed != password

    # Should verify correctly
    assert verify_password(password, hashed) is True

    # Should not verify incorrect password
    assert verify_password("wrong_password", hashed) is False


def test_create_and_decode_jwt_token():
    """Test JWT token creation and decoding"""
    settings = get_settings()

    # Create token
    data = {
        "sub": "test_user",
        "scopes": ["verify", "admin"]
    }
    token = create_access_token(data)

    # Token should be a string
    assert isinstance(token, str)
    assert len(token) > 0

    # Decode token
    token_data = decode_access_token(token)

    # Check claims
    assert token_data.sub == "test_user"
    assert token_data.scopes == ["verify", "admin"]
    assert isinstance(token_data.exp, datetime)
    assert isinstance(token_data.iat, datetime)


def test_jwt_token_expiration():
    """Test JWT token expiration handling"""
    # Create token that expires in 1 second
    data = {"sub": "test_user"}
    expires_delta = timedelta(seconds=-1)  # Already expired
    token = create_access_token(data, expires_delta)

    # Decoding expired token should raise exception
    with pytest.raises(Exception):  # HTTPException from jose
        decode_access_token(token)


def test_jwt_token_custom_expiration():
    """Test JWT token with custom expiration"""
    data = {"sub": "test_user"}
    expires_delta = timedelta(hours=1)
    token = create_access_token(data, expires_delta)

    # Decode and check expiration
    token_data = decode_access_token(token)
    time_diff = token_data.exp - token_data.iat

    # Should be approximately 1 hour
    assert 3590 < time_diff.total_seconds() < 3610


def test_api_key_registration():
    """Test API key registration"""
    api_key = register_api_key(
        key_id="test_key_1",
        user_id="test_user",
        scopes=["verify"],
        rate_limit=100
    )

    # API key should be a string starting with 'ak_'
    assert isinstance(api_key, str)
    assert api_key.startswith("ak_")
    assert len(api_key) > 10


def test_api_key_verification():
    """Test API key verification"""
    # Register a key
    api_key = register_api_key(
        key_id="test_key_2",
        user_id="test_user",
        scopes=["verify"],
        rate_limit=60
    )

    # Verify the key
    key_data = verify_api_key(api_key)

    assert key_data is not None
    assert key_data.key_id == "test_key_2"
    assert key_data.user_id == "test_user"
    assert key_data.scopes == ["verify"]
    assert key_data.rate_limit == 60


def test_api_key_invalid():
    """Test invalid API key returns None"""
    key_data = verify_api_key("invalid_key_12345")
    assert key_data is None


def test_api_key_expiration():
    """Test API key expiration"""
    # Register key that's already expired
    expires_at = datetime.utcnow() - timedelta(days=1)

    api_key = register_api_key(
        key_id="test_key_expired",
        user_id="test_user",
        scopes=["verify"],
        expires_at=expires_at
    )

    # Verify should return None for expired key
    key_data = verify_api_key(api_key)
    assert key_data is None


def test_api_key_custom_rate_limit():
    """Test API key with custom rate limit"""
    api_key = register_api_key(
        key_id="test_key_custom_limit",
        user_id="test_user",
        scopes=["verify", "admin"],
        rate_limit=500
    )

    key_data = verify_api_key(api_key)

    assert key_data.rate_limit == 500
    assert key_data.scopes == ["verify", "admin"]
