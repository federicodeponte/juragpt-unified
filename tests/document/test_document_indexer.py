"""
Tests for DocumentIndexerService
Phase 18: Service class refactoring tests
"""

import pytest
import uuid
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from fastapi import HTTPException, UploadFile

from app.services.document_indexer import DocumentIndexerService
from app.auth.models import User
from app.core.file_detector import FileType


class TestDocumentIndexerService:
    """Test DocumentIndexerService methods"""

    @pytest.fixture
    def service(self):
        """Create service instance"""
        return DocumentIndexerService()

    @pytest.fixture
    def mock_user(self):
        """Create mock user"""
        from datetime import datetime
        return User(id=uuid.uuid4(), email="test@example.com", created_at=datetime.utcnow())

    @pytest.fixture
    def mock_upload_file(self):
        """Create mock upload file"""
        file = Mock(spec=UploadFile)
        file.filename = "test.pdf"
        file.content_type = "application/pdf"
        file.read = AsyncMock(return_value=b"PDF content")
        return file

    # ========================================================================
    # Test _enforce_limits()
    # ========================================================================

    @pytest.mark.asyncio
    async def test_enforce_limits_success(self, service, mock_user):
        """Test successful rate limit and quota enforcement"""
        with patch("app.services.document_indexer.rate_limiter") as mock_rate, \
             patch("app.services.document_indexer.usage_tracker") as mock_usage:

            mock_rate.enforce_rate_limit = AsyncMock()
            mock_usage.enforce_quota = AsyncMock()

            await service._enforce_limits(mock_user)

            mock_rate.enforce_rate_limit.assert_called_once_with(str(mock_user.id), "index")
            mock_usage.enforce_quota.assert_called_once_with(mock_user.id, "documents", 1)

    @pytest.mark.asyncio
    async def test_enforce_limits_rate_limit_exceeded(self, service, mock_user):
        """Test rate limit exceeded raises HTTPException"""
        with patch("app.services.document_indexer.rate_limiter") as mock_rate:
            mock_rate.enforce_rate_limit = AsyncMock(
                side_effect=HTTPException(status_code=429, detail="Rate limit exceeded")
            )

            with pytest.raises(HTTPException) as exc_info:
                await service._enforce_limits(mock_user)

            assert exc_info.value.status_code == 429

    # ========================================================================
    # Test _handle_duplicate_check()
    # ========================================================================

    @pytest.mark.asyncio
    async def test_handle_duplicate_check_no_duplicate(self, service):
        """Test when document does not exist"""
        doc_hash = "abc123"
        request_id = "req-123"

        with patch("app.services.document_indexer.supabase_client") as mock_supabase:
            mock_supabase.document_exists = AsyncMock(return_value=False)

            # Should not raise
            await service._handle_duplicate_check(doc_hash, request_id)

            mock_supabase.document_exists.assert_called_once_with(doc_hash)

    @pytest.mark.asyncio
    async def test_handle_duplicate_check_with_duplicate(self, service):
        """Test when document already exists"""
        doc_hash = "abc123"
        request_id = "req-123"

        with patch("app.services.document_indexer.supabase_client") as mock_supabase, \
             patch("app.services.document_indexer.redis_client") as mock_redis, \
             patch("app.services.document_indexer.settings") as mock_settings:

            mock_supabase.document_exists = AsyncMock(return_value=True)
            mock_settings.cache_enabled = True
            mock_redis.invalidate_cache = Mock(return_value=5)

            with pytest.raises(HTTPException) as exc_info:
                await service._handle_duplicate_check(doc_hash, request_id)

            assert exc_info.value.status_code == 409
            assert "already indexed" in exc_info.value.detail
            mock_redis.invalidate_cache.assert_called_once_with(f"doc:{doc_hash}*")

    @pytest.mark.asyncio
    async def test_handle_duplicate_check_cache_disabled(self, service):
        """Test duplicate check when cache is disabled"""
        doc_hash = "abc123"
        request_id = "req-123"

        with patch("app.services.document_indexer.supabase_client") as mock_supabase, \
             patch("app.services.document_indexer.redis_client") as mock_redis, \
             patch("app.services.document_indexer.settings") as mock_settings:

            mock_supabase.document_exists = AsyncMock(return_value=True)
            mock_settings.cache_enabled = False

            with pytest.raises(HTTPException):
                await service._handle_duplicate_check(doc_hash, request_id)

            # Should not call invalidate_cache
            mock_redis.invalidate_cache.assert_not_called()

    # ========================================================================
    # Test _store_original_file()
    # ========================================================================

    def test_store_original_file(self, service):
        """Test file storage"""
        content = b"PDF content"
        doc_hash = "abc123"
        filename = "test.pdf"
        user_id = uuid.uuid4()
        file_analysis = {"file_type": "pdf", "total_pages": 5}

        with patch("app.services.document_indexer.file_storage") as mock_storage:
            mock_storage.store_file = Mock(return_value="storage/path/abc123.pdf")

            result = service._store_original_file(
                content, doc_hash, filename, user_id, file_analysis
            )

            assert result == "storage/path/abc123.pdf"
            mock_storage.store_file.assert_called_once_with(
                file_content=content,
                file_hash=doc_hash,
                filename=filename,
                user_id=str(user_id),
                metadata=file_analysis,
            )

    # ========================================================================
    # Test _extract_text()
    # ========================================================================

    @pytest.mark.asyncio
    async def test_extract_text_docx(self, service):
        """Test DOCX text extraction"""
        content = b"DOCX content"
        file_analysis = {"file_type": "docx"}

        with patch("app.services.document_indexer.docx_extractor") as mock_extractor:
            mock_extractor.extract_text = Mock(return_value="Extracted DOCX text")

            text, metadata = await service._extract_text(
                content, FileType.DOCX, file_analysis, "application/docx", "req-123"
            )

            assert text == "Extracted DOCX text"
            assert metadata["extraction_method"] == "docx"

    @pytest.mark.asyncio
    async def test_extract_text_eml(self, service):
        """Test EML text extraction"""
        content = b"EML content"
        file_analysis = {"file_type": "eml"}

        with patch("app.services.document_indexer.email_extractor") as mock_extractor:
            mock_extractor.extract_text_only = Mock(return_value="Extracted email text")

            text, metadata = await service._extract_text(
                content, FileType.EML, file_analysis, "message/rfc822", "req-123"
            )

            assert text == "Extracted email text"
            assert metadata["extraction_method"] == "email"

    @pytest.mark.asyncio
    async def test_extract_text_empty_content_docx(self, service):
        """Test extraction failure with empty DOCX content"""
        content = b"DOCX bytes"
        file_analysis = {"file_type": "docx"}

        with patch("app.services.document_indexer.docx_extractor") as mock_extractor:
            # Mock returns empty string
            mock_extractor.extract_text = Mock(return_value="   ")

            with pytest.raises(HTTPException) as exc_info:
                await service._extract_text(
                    content, FileType.DOCX, file_analysis, "application/docx", "req-123"
                )

            assert exc_info.value.status_code == 400
            assert "No text could be extracted" in exc_info.value.detail

    # ========================================================================
    # Test _merge_ocr_and_embedded()
    # ========================================================================

    def test_merge_ocr_and_embedded(self, service):
        """Test merging OCR with embedded text"""
        pages = [Mock(text="Page 1"), Mock(text="Page 2")]

        ocr_result = Mock()
        ocr_result.avg_confidence = 0.95
        ocr_result.total_processing_time_ms = 1500
        ocr_result.typed_text_pct = 90.0
        ocr_result.handwritten_text_pct = 10.0
        ocr_result.pages_processed = 2
        ocr_result.pages_failed = 0
        ocr_result.errors = []

        merged = Mock()
        merged.full_text = "Merged text"
        merged.avg_confidence = 0.92
        merged.stats = {"pages": 2, "merged_sections": 10}

        base_metadata = {"total_pages": 2}

        with patch("app.services.document_indexer.text_merger") as mock_merger:
            mock_merger.merge_document = Mock(return_value=merged)

            text, metadata = service._merge_ocr_and_embedded(
                pages, ocr_result, "high", base_metadata, "req-123"
            )

            assert text == "Merged text"
            assert metadata["extraction_method"] == "merged"
            assert metadata["merge_avg_confidence"] == 0.92
            assert metadata["ocr_avg_confidence"] == 0.95
            assert metadata["ocr_pages_processed"] == 2

    # ========================================================================
    # Test _use_ocr_only()
    # ========================================================================

    def test_use_ocr_only(self, service):
        """Test OCR-only extraction"""
        ocr_result = Mock()
        ocr_result.full_text = "OCR extracted text"
        ocr_result.avg_confidence = 0.88
        ocr_result.total_processing_time_ms = 2000
        ocr_result.typed_text_pct = 85.0
        ocr_result.handwritten_text_pct = 15.0
        ocr_result.pages_processed = 3
        ocr_result.pages_failed = 1
        ocr_result.errors = ["Page 4 failed"]

        base_metadata = {"total_pages": 4}

        text, metadata = service._use_ocr_only(ocr_result, base_metadata, "req-123")

        assert text == "OCR extracted text"
        assert metadata["extraction_method"] == "modal_ocr"
        assert metadata["ocr_avg_confidence"] == 0.88
        assert metadata["ocr_pages_processed"] == 3
        assert metadata["ocr_pages_failed"] == 1

    # ========================================================================
    # Test _create_document_record()
    # ========================================================================

    @pytest.mark.asyncio
    async def test_create_document_record(self, service):
        """Test document record creation"""
        user_id = uuid.uuid4()
        doc_id = uuid.uuid4()

        mock_doc = Mock()
        mock_doc.id = doc_id
        mock_doc.filename = "test.pdf"

        with patch("app.services.document_indexer.supabase_client") as mock_supabase:
            mock_supabase.create_document = AsyncMock(return_value=mock_doc)

            result = await service._create_document_record(
                user_id=user_id,
                filename="test.pdf",
                doc_hash="abc123",
                file_size_bytes=1024,
                content_type="application/pdf",
                file_type=FileType.PDF,
                storage_path="storage/abc123.pdf",
                file_analysis={"total_pages": 5},
                extraction_metadata={"extraction_method": "embedded_text"},
            )

            assert result.id == doc_id
            assert result.filename == "test.pdf"

            # Verify create_document was called with correct merged metadata
            call_args = mock_supabase.create_document.call_args
            assert call_args[1]["user_id"] == user_id
            assert call_args[1]["filename"] == "test.pdf"
            assert call_args[1]["metadata"]["total_pages"] == 5
            assert call_args[1]["metadata"]["extraction_method"] == "embedded_text"

    # ========================================================================
    # Test _parse_and_embed()
    # ========================================================================

    @pytest.mark.asyncio
    async def test_parse_and_embed(self, service):
        """Test document parsing and embedding"""
        text = "§5 Test section\nContent here."
        document_id = uuid.uuid4()

        mock_sections = [
            {"section_id": "§5", "content": "Test section"},
            {"section_id": "§6", "content": "Another section"},
        ]

        mock_chunks = [
            {"id": uuid.uuid4(), "content": "Chunk 1"},
            {"id": uuid.uuid4(), "content": "Chunk 2"},
        ]

        # Mock retriever at the module level where it's imported locally
        with patch.object(service.parser, "parse_document") as mock_parse, \
             patch.object(service.parser, "create_chunks_for_embedding") as mock_create_chunks, \
             patch("app.core.retriever.retriever") as mock_retriever:

            mock_parse.return_value = mock_sections
            mock_create_chunks.return_value = mock_chunks
            mock_retriever.index_document_chunks = AsyncMock(return_value=2)

            chunks_created = await service._parse_and_embed(text, document_id, "req-123")

            assert chunks_created == 2
            mock_parse.assert_called_once_with(text)
            mock_create_chunks.assert_called_once_with(mock_sections, document_id)
            mock_retriever.index_document_chunks.assert_called_once_with(mock_chunks, document_id)

    # ========================================================================
    # Test index_document() integration
    # ========================================================================

    @pytest.mark.asyncio
    async def test_index_document_success(self, service, mock_user, mock_upload_file):
        """Test successful document indexing (integration)"""
        request_id = "req-123"
        doc_id = uuid.uuid4()

        # Mock all dependencies
        with patch("app.services.document_indexer.rate_limiter") as mock_rate, \
             patch("app.services.document_indexer.usage_tracker") as mock_usage, \
             patch("app.services.document_indexer.validate_file") as mock_validate, \
             patch("app.services.document_indexer.file_detector") as mock_detector, \
             patch("app.services.document_indexer.supabase_client") as mock_supabase, \
             patch("app.services.document_indexer.file_storage") as mock_storage, \
             patch("app.services.document_indexer.docx_extractor") as mock_extractor, \
             patch.object(service.parser, "parse_document") as mock_parse, \
             patch.object(service.parser, "create_chunks_for_embedding") as mock_chunks, \
             patch("app.core.retriever.retriever") as mock_retriever:

            # Setup mocks
            mock_rate.enforce_rate_limit = AsyncMock()
            mock_usage.enforce_quota = AsyncMock()
            mock_usage.increment_usage = AsyncMock()
            mock_validate.return_value = None

            mock_detector.analyze_file = Mock(return_value={
                "file_hash": "abc123",
                "file_type": "docx",
            })

            mock_supabase.document_exists = AsyncMock(return_value=False)
            mock_doc = Mock()
            mock_doc.id = doc_id
            mock_supabase.create_document = AsyncMock(return_value=mock_doc)

            mock_storage.store_file = Mock(return_value="storage/abc123.docx")
            mock_extractor.extract_text = Mock(return_value="Extracted text content")

            mock_parse.return_value = [{"section_id": "§1", "content": "Test"}]
            mock_chunks.return_value = [{"id": uuid.uuid4()}]
            mock_retriever.index_document_chunks = AsyncMock(return_value=1)

            # Execute
            result = await service.index_document(mock_upload_file, mock_user, request_id)

            # Verify
            assert result["document_id"] == doc_id
            assert result["chunks_created"] == 1
            assert result["status"] == "indexed"
            assert result["filename"] == "test.pdf"

    @pytest.mark.asyncio
    async def test_index_document_handles_errors(self, service, mock_user, mock_upload_file):
        """Test error handling in index_document"""
        request_id = "req-123"

        with patch("app.services.document_indexer.rate_limiter") as mock_rate:
            mock_rate.enforce_rate_limit = AsyncMock(
                side_effect=Exception("Database error")
            )

            with pytest.raises(HTTPException) as exc_info:
                await service.index_document(mock_upload_file, mock_user, request_id)

            assert exc_info.value.status_code == 500
            assert "Indexing failed" in exc_info.value.detail
