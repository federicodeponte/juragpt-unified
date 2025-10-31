"""Tests for input validation and sanitization"""

import pytest
import uuid
from fastapi import HTTPException
from unittest.mock import Mock, AsyncMock

from app.utils.validators import (
    FileValidator,
    InputValidator,
    validate_uuid,
    sanitize_query,
    validate_top_k,
    sanitize_metadata,
)


class TestFileValidator:
    """Test file upload validation"""

    @pytest.mark.asyncio
    async def test_validate_file_success(self):
        """Test successful file validation"""
        # Create mock file
        mock_file = Mock()
        mock_file.filename = "test_document.pdf"
        mock_file.content_type = "application/pdf"
        mock_file.read = AsyncMock(return_value=b"PDF file content here")
        mock_file.seek = AsyncMock()

        # Should not raise
        await FileValidator.validate_file(mock_file)

    @pytest.mark.asyncio
    async def test_validate_file_no_filename(self):
        """Test file validation fails with no filename"""
        mock_file = Mock()
        mock_file.filename = None

        with pytest.raises(HTTPException) as exc:
            await FileValidator.validate_file(mock_file)

        assert exc.value.status_code == 400
        assert "Filename is required" in exc.value.detail

    @pytest.mark.asyncio
    async def test_validate_file_invalid_extension(self):
        """Test file validation fails with invalid extension"""
        mock_file = Mock()
        mock_file.filename = "malware.exe"
        mock_file.content_type = "application/x-executable"

        with pytest.raises(HTTPException) as exc:
            await FileValidator.validate_file(mock_file)

        assert exc.value.status_code == 400
        assert "not supported" in exc.value.detail

    @pytest.mark.asyncio
    async def test_validate_file_empty(self):
        """Test file validation fails for empty file"""
        mock_file = Mock()
        mock_file.filename = "empty.pdf"
        mock_file.read = AsyncMock(return_value=b"")

        with pytest.raises(HTTPException) as exc:
            await FileValidator.validate_file(mock_file)

        assert exc.value.status_code == 400
        assert "empty" in exc.value.detail.lower()

    @pytest.mark.asyncio
    async def test_validate_file_too_large(self):
        """Test file validation fails for files exceeding size limit"""
        # Create 60MB file (exceeds 50MB limit)
        large_content = b"x" * (60 * 1024 * 1024)

        mock_file = Mock()
        mock_file.filename = "large.pdf"
        mock_file.read = AsyncMock(return_value=large_content)

        with pytest.raises(HTTPException) as exc:
            await FileValidator.validate_file(mock_file)

        assert exc.value.status_code == 413
        assert "too large" in exc.value.detail.lower()

    def test_sanitize_filename(self):
        """Test filename sanitization"""
        # Normal filename
        assert FileValidator.sanitize_filename("document.pdf") == "document.pdf"

        # German umlauts (should be preserved)
        assert FileValidator.sanitize_filename("Müller_Urteil.pdf") == "Müller_Urteil.pdf"

        # Directory traversal attack
        assert FileValidator.sanitize_filename("../../../etc/passwd") == ""

        # Null bytes
        assert FileValidator.sanitize_filename("file\x00.pdf") == ""

        # Special characters (should be replaced with underscore)
        assert FileValidator.sanitize_filename("file:name?.pdf") == "file_name_.pdf"

        # Empty after sanitization
        assert FileValidator.sanitize_filename("???") == "unnamed_file"

        # Very long filename (should be truncated)
        long_name = "a" * 300 + ".pdf"
        sanitized = FileValidator.sanitize_filename(long_name)
        assert len(sanitized) <= 200


class TestInputValidator:
    """Test input validation and sanitization"""

    def test_validate_uuid_success(self):
        """Test successful UUID validation"""
        valid_uuid = str(uuid.uuid4())
        result = InputValidator.validate_uuid(valid_uuid, "test_id")
        assert isinstance(result, uuid.UUID)
        assert str(result) == valid_uuid

    def test_validate_uuid_invalid(self):
        """Test UUID validation fails for invalid format"""
        with pytest.raises(HTTPException) as exc:
            InputValidator.validate_uuid("not-a-uuid", "test_id")

        assert exc.value.status_code == 400
        assert "Invalid test_id format" in exc.value.detail

    def test_sanitize_query_success(self):
        """Test successful query sanitization"""
        query = "Was regelt §5.2?"
        result = InputValidator.sanitize_query(query)
        assert result == query

    def test_sanitize_query_empty(self):
        """Test query validation fails for empty query"""
        with pytest.raises(HTTPException) as exc:
            InputValidator.sanitize_query("")

        assert exc.value.status_code == 400
        assert "cannot be empty" in exc.value.detail

    def test_sanitize_query_whitespace_only(self):
        """Test query validation fails for whitespace-only query"""
        with pytest.raises(HTTPException) as exc:
            InputValidator.sanitize_query("   \n\t   ")

        assert exc.value.status_code == 400
        assert "cannot be empty" in exc.value.detail

    def test_sanitize_query_too_long(self):
        """Test query validation fails for excessively long queries"""
        long_query = "a" * 1001

        with pytest.raises(HTTPException) as exc:
            InputValidator.sanitize_query(long_query)

        assert exc.value.status_code == 400
        assert "too long" in exc.value.detail.lower()

    def test_sanitize_query_removes_null_bytes(self):
        """Test query sanitization removes null bytes"""
        query = "Valid query\x00with null"
        result = InputValidator.sanitize_query(query)
        assert "\x00" not in result
        assert result == "Valid querywith null"

    def test_sanitize_query_sql_injection_attempt(self):
        """Test query sanitization with SQL injection patterns (logged, not blocked)"""
        # These should be logged but not blocked (parameterized queries protect us)
        sql_queries = [
            "' OR '1'='1",
            "'; DROP TABLE users--",
            "' UNION SELECT * FROM passwords",
        ]

        for sql_query in sql_queries:
            # Should not raise (parameterized queries handle this)
            result = InputValidator.sanitize_query(sql_query)
            assert result == sql_query  # Returned as-is, but logged

    def test_validate_top_k_default(self):
        """Test top_k validation with default value"""
        result = InputValidator.validate_top_k(None, default=5)
        assert result == 5

    def test_validate_top_k_valid(self):
        """Test top_k validation with valid value"""
        result = InputValidator.validate_top_k(10)
        assert result == 10

    def test_validate_top_k_too_small(self):
        """Test top_k validation fails for values < 1"""
        with pytest.raises(HTTPException) as exc:
            InputValidator.validate_top_k(0)

        assert exc.value.status_code == 400
        assert "at least 1" in exc.value.detail

    def test_validate_top_k_too_large(self):
        """Test top_k validation fails for values > max"""
        with pytest.raises(HTTPException) as exc:
            InputValidator.validate_top_k(100, max_value=20)

        assert exc.value.status_code == 400
        assert "too large" in exc.value.detail.lower()

    def test_sanitize_metadata_success(self):
        """Test successful metadata sanitization"""
        metadata = {
            "user": "test",
            "count": 42,
            "ratio": 3.14,
            "enabled": True,
        }

        result = InputValidator.sanitize_metadata(metadata)
        assert result == metadata

    def test_sanitize_metadata_invalid_type(self):
        """Test metadata validation fails for non-dict input"""
        with pytest.raises(HTTPException) as exc:
            InputValidator.sanitize_metadata("not a dict")

        assert exc.value.status_code == 400
        assert "must be a JSON object" in exc.value.detail

    def test_sanitize_metadata_too_many_keys(self):
        """Test metadata validation fails for excessive keys"""
        metadata = {f"key_{i}": i for i in range(100)}

        with pytest.raises(HTTPException) as exc:
            InputValidator.sanitize_metadata(metadata, max_keys=50)

        assert exc.value.status_code == 400
        assert "Too many metadata keys" in exc.value.detail

    def test_sanitize_metadata_sanitizes_keys(self):
        """Test metadata key sanitization"""
        metadata = {"user-name": "test", "count@123": 42}

        result = InputValidator.sanitize_metadata(metadata)
        assert "user_name" in result
        assert "count_123" in result

    def test_sanitize_metadata_truncates_strings(self):
        """Test metadata string value truncation"""
        long_value = "a" * 1000
        metadata = {"description": long_value}

        result = InputValidator.sanitize_metadata(metadata, max_value_length=100)
        assert len(result["description"]) == 100

    def test_sanitize_metadata_converts_complex_types(self):
        """Test metadata complex type conversion"""
        metadata = {
            "list": [1, 2, 3],
            "dict": {"nested": "value"},
        }

        result = InputValidator.sanitize_metadata(metadata)
        assert isinstance(result["list"], str)
        assert isinstance(result["dict"], str)


class TestConvenienceAliases:
    """Test convenience function aliases"""

    def test_validate_uuid_alias(self):
        """Test validate_uuid is an alias"""
        valid_uuid = str(uuid.uuid4())
        result = validate_uuid(valid_uuid)
        assert isinstance(result, uuid.UUID)

    def test_sanitize_query_alias(self):
        """Test sanitize_query is an alias"""
        result = sanitize_query("Test query")
        assert result == "Test query"

    def test_validate_top_k_alias(self):
        """Test validate_top_k is an alias"""
        result = validate_top_k(10)
        assert result == 10

    def test_sanitize_metadata_alias(self):
        """Test sanitize_metadata is an alias"""
        metadata = {"key": "value"}
        result = sanitize_metadata(metadata)
        assert result == metadata
