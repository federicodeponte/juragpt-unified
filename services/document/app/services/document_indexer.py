"""
ABOUTME: Document indexing service - orchestrates document parsing, extraction, and embedding
ABOUTME: Separates business logic from API routing (SOLID: Single Responsibility Principle)
"""

import time
import uuid
from typing import Dict, Tuple

from fastapi import HTTPException, UploadFile

from app.auth.models import User
from app.auth.rate_limit import rate_limiter
from app.auth.usage import usage_tracker
from app.config import settings
from app.core.document_parser import DocumentParser
from app.core.docx_extractor import docx_extractor
from app.core.email_extractor import email_extractor
from app.core.file_detector import file_detector, FileType
from app.core.pdf_extractor import pdf_extractor
from app.core.text_merger import text_merger
# Note: retriever imported locally in _parse_and_embed to avoid circular imports
from app.db.models import DocumentDB
from app.db.supabase_client import supabase_client
from app.services.modal_client import modal_ocr_client
from app.utils.file_storage import file_storage
from app.utils.logging import log_error, logger
from app.utils.redis_client import redis_client
from app.utils.validators import validate_file


class DocumentIndexerService:
    """
    Service class for document indexing operations

    Responsibilities:
    - Orchestrate document processing pipeline
    - Handle file extraction (PDF, DOCX, EML)
    - Manage OCR processing when needed
    - Parse document into sections and chunks
    - Generate and store embeddings
    """

    def __init__(self):
        self.parser = DocumentParser()

    async def index_document(
        self, file: UploadFile, user: User, request_id: str
    ) -> Dict:
        """
        Index a document through the full pipeline

        Args:
            file: Uploaded file
            user: Authenticated user
            request_id: Request tracking ID

        Returns:
            Dict with indexing results (document_id, chunks_created, etc.)

        Raises:
            HTTPException: On indexing failures
        """
        start_time = time.time()

        try:
            # Step 1: Enforce rate limits and quotas
            await self._enforce_limits(user)

            # Step 2: Validate file upload
            await validate_file(file)
            filename = file.filename or "unnamed_document"

            logger.info(
                f"Starting document indexing: {filename}",
                extra={"request_id": request_id},
            )

            # Step 3: Read and analyze file
            content = await file.read()
            file_analysis = file_detector.analyze_file(content, filename)
            doc_hash = file_analysis["file_hash"]
            detected_type = FileType(file_analysis["file_type"])

            logger.info(f"Detected file type: {detected_type.value}")

            # Step 4: Check for duplicates and invalidate cache
            await self._handle_duplicate_check(doc_hash, request_id)

            # Step 5: Store original file
            storage_path = self._store_original_file(
                content, doc_hash, filename, user.id, file_analysis
            )

            # Step 6: Extract text based on file type
            text, extraction_metadata = await self._extract_text(
                content, detected_type, file_analysis, file.content_type, request_id
            )

            # Step 7: Create document record
            document = await self._create_document_record(
                user.id,
                filename,
                doc_hash,
                len(content),
                file.content_type,
                detected_type,
                storage_path,
                file_analysis,
                extraction_metadata,
            )

            # Step 8: Parse, chunk, and embed
            chunks_created = await self._parse_and_embed(text, document.id, request_id)

            # Step 9: Track usage
            await usage_tracker.increment_usage(user.id, documents=1)

            latency_ms = int((time.time() - start_time) * 1000)

            logger.info(
                f"Document indexed successfully: {chunks_created} chunks",
                extra={
                    "request_id": request_id,
                    "document_id": str(document.id),
                    "latency_ms": latency_ms,
                },
            )

            return {
                "document_id": document.id,
                "filename": filename,
                "chunks_created": chunks_created,
                "status": "indexed",
                "message": f"Document indexed successfully with {chunks_created} chunks",
            }

        except Exception as e:
            log_error(e, request_id=request_id)
            raise HTTPException(status_code=500, detail=f"Indexing failed: {str(e)}")

    async def _enforce_limits(self, user: User) -> None:
        """Enforce rate limiting and quota limits"""
        await rate_limiter.enforce_rate_limit(str(user.id), "index")
        await usage_tracker.enforce_quota(user.id, "documents", 1)

    async def _handle_duplicate_check(self, doc_hash: str, request_id: str) -> None:
        """Check for duplicate documents and invalidate cache if needed"""
        if await supabase_client.document_exists(doc_hash):
            # Invalidate cache for this document (if it's being replaced)
            if settings.cache_enabled:
                redis_client.invalidate_cache(f"doc:{doc_hash}*")
                logger.info(
                    f"Invalidated cache for document hash: {doc_hash}",
                    extra={"request_id": request_id},
                )
            raise HTTPException(status_code=409, detail="Document already indexed")

    def _store_original_file(
        self,
        content: bytes,
        doc_hash: str,
        filename: str,
        user_id: uuid.UUID,
        file_analysis: Dict,
    ) -> str:
        """Store original file in Supabase Storage"""
        return file_storage.store_file(
            file_content=content,
            file_hash=doc_hash,
            filename=filename,
            user_id=str(user_id),
            metadata=file_analysis,
        )

    async def _extract_text(
        self,
        content: bytes,
        detected_type: FileType,
        file_analysis: Dict,
        content_type: str | None,
        request_id: str,
    ) -> Tuple[str, Dict]:
        """
        Extract text from document based on file type

        Returns:
            Tuple of (extracted_text, extraction_metadata)
        """
        text = ""
        extraction_metadata = {}

        if detected_type == FileType.PDF:
            text, extraction_metadata = await self._extract_pdf_text(
                content, file_analysis, request_id
            )

        elif detected_type == FileType.DOCX:
            text = docx_extractor.extract_text(content)
            extraction_metadata = {"extraction_method": "docx"}

        elif detected_type == FileType.EML:
            text = email_extractor.extract_text_only(content)
            extraction_metadata = {"extraction_method": "email"}

        else:
            # Fallback to UTF-8 decode
            text = content.decode("utf-8", errors="ignore")
            extraction_metadata = {"extraction_method": "utf8_decode"}

        # Validate extracted text
        if not text or len(text.strip()) < 10:
            raise HTTPException(
                status_code=400,
                detail=f"No text could be extracted from {detected_type.value} file",
            )

        return text, extraction_metadata

    async def _extract_pdf_text(
        self, content: bytes, file_analysis: Dict, request_id: str
    ) -> Tuple[str, Dict]:
        """
        Extract text from PDF with OCR support

        Returns:
            Tuple of (extracted_text, extraction_metadata)
        """
        # Extract embedded text first
        pages = pdf_extractor.extract_embedded_text(content)
        embedded_text = "\n\n".join(page.text for page in pages if page.text)

        extraction_metadata = {
            "total_pages": file_analysis.get("total_pages", 0),
            "text_layer_quality": file_analysis.get("text_layer_quality"),
            "needs_ocr": file_analysis.get("needs_ocr", False),
            "extraction_method": "embedded_text",
        }

        # Check if OCR is needed and available
        if file_analysis.get("needs_ocr") and modal_ocr_client.is_available():
            logger.info(
                f"Running OCR (quality: {file_analysis.get('text_layer_quality')})",
                extra={"request_id": request_id},
            )
            try:
                ocr_result = await modal_ocr_client.process_document_ocr(
                    content,
                    enable_handwriting=settings.enable_handwriting_ocr,
                    request_id=request_id,
                )

                if ocr_result.pages_processed > 0:
                    # Merge OCR with embedded text if available
                    if embedded_text and pages:
                        text, extraction_metadata = self._merge_ocr_and_embedded(
                            pages,
                            ocr_result,
                            file_analysis.get("text_layer_quality", "unknown"),
                            extraction_metadata,
                            request_id,
                        )
                    else:
                        # Use OCR only
                        text, extraction_metadata = self._use_ocr_only(
                            ocr_result, extraction_metadata, request_id
                        )
                else:
                    # OCR failed all pages
                    text = embedded_text
                    extraction_metadata["extraction_method"] = (
                        "embedded_text_ocr_failed"
                    )
                    extraction_metadata["ocr_errors"] = ocr_result.errors[:5]
                    logger.error(
                        "OCR failed all pages, using embedded",
                        extra={"request_id": request_id},
                    )

                return text, extraction_metadata

            except Exception as e:
                # OCR error fallback
                text = embedded_text
                extraction_metadata["extraction_method"] = "embedded_text_ocr_error"
                extraction_metadata["ocr_error"] = str(e)
                logger.error(
                    f"OCR error: {e}, using embedded", extra={"request_id": request_id}
                )
                return text, extraction_metadata

        elif file_analysis.get("needs_ocr") and not modal_ocr_client.is_available():
            # OCR needed but unavailable
            extraction_metadata["extraction_method"] = "embedded_text_ocr_unavailable"
            logger.warning("OCR needed but unavailable", extra={"request_id": request_id})

        return embedded_text, extraction_metadata

    def _merge_ocr_and_embedded(
        self, pages, ocr_result, text_layer_quality, base_metadata, request_id
    ) -> Tuple[str, Dict]:
        """Merge OCR results with embedded text"""
        merged = text_merger.merge_document(
            pages, ocr_result, text_layer_quality, request_id
        )

        extraction_metadata = {
            **base_metadata,
            "needs_ocr": True,
            "extraction_method": "merged",
            "merge_avg_confidence": merged.avg_confidence,
            "merge_stats": merged.stats,
            "ocr_avg_confidence": ocr_result.avg_confidence,
            "ocr_processing_time_ms": ocr_result.total_processing_time_ms,
            "ocr_typed_text_pct": ocr_result.typed_text_pct,
            "ocr_handwritten_text_pct": ocr_result.handwritten_text_pct,
            "ocr_pages_processed": ocr_result.pages_processed,
            "ocr_pages_failed": ocr_result.pages_failed,
            "ocr_errors": ocr_result.errors[:5] if ocr_result.errors else [],
        }

        logger.info(
            f"Merged text: {merged.stats}, conf: {merged.avg_confidence:.2f}",
            extra={"request_id": request_id},
        )

        return merged.full_text, extraction_metadata

    def _use_ocr_only(
        self, ocr_result, base_metadata, request_id
    ) -> Tuple[str, Dict]:
        """Use OCR results only (no embedded text)"""
        extraction_metadata = {
            **base_metadata,
            "needs_ocr": True,
            "extraction_method": "modal_ocr",
            "ocr_avg_confidence": ocr_result.avg_confidence,
            "ocr_processing_time_ms": ocr_result.total_processing_time_ms,
            "ocr_typed_text_pct": ocr_result.typed_text_pct,
            "ocr_handwritten_text_pct": ocr_result.handwritten_text_pct,
            "ocr_pages_processed": ocr_result.pages_processed,
            "ocr_pages_failed": ocr_result.pages_failed,
            "ocr_errors": ocr_result.errors[:5] if ocr_result.errors else [],
        }

        logger.info(
            f"OCR done: {ocr_result.pages_processed} pages, "
            f"conf: {ocr_result.avg_confidence:.2f}",
            extra={"request_id": request_id},
        )

        return ocr_result.full_text, extraction_metadata

    async def _create_document_record(
        self,
        user_id: uuid.UUID,
        filename: str,
        doc_hash: str,
        file_size_bytes: int,
        content_type: str | None,
        file_type: FileType,
        storage_path: str,
        file_analysis: Dict,
        extraction_metadata: Dict,
    ) -> DocumentDB:
        """Create document record in database"""
        return await supabase_client.create_document(
            user_id=user_id,
            filename=filename,
            doc_hash=doc_hash,
            file_size_bytes=file_size_bytes,
            metadata={
                "content_type": content_type,
                "file_type": file_type.value,
                "storage_path": storage_path,
                **file_analysis,
                **extraction_metadata,
            },
        )

    async def _parse_and_embed(
        self, text: str, document_id: uuid.UUID, request_id: str
    ) -> int:
        """
        Parse document into sections, create chunks, and generate embeddings

        Returns:
            Number of chunks created
        """
        # Import retriever locally to avoid circular imports and enable testing
        from app.core.retriever import retriever

        # Parse document into hierarchical sections
        sections = self.parser.parse_document(text)

        logger.info(f"Parsed {len(sections)} sections from document")

        # Create chunks for embedding
        chunks = self.parser.create_chunks_for_embedding(sections, document_id)

        # Generate embeddings and store in database
        chunks_created = await retriever.index_document_chunks(chunks, document_id)

        return chunks_created


# Global service instance
document_indexer = DocumentIndexerService()
