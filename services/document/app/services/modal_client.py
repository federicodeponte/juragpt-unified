"""
ABOUTME: Modal OCR client for GPU-accelerated document text extraction
ABOUTME: Integrates docTR (typed text) + TrOCR (handwritten text) via Modal serverless GPU
"""

import asyncio
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

try:
    import modal

    MODAL_AVAILABLE = True
except ImportError:
    MODAL_AVAILABLE = False

from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import settings
from app.utils.logging import logger


@dataclass
class OCRPageResult:
    page_num: int
    full_text: str
    avg_confidence: float
    typed_text_pct: float
    handwritten_text_pct: float
    processing_time_ms: int
    regions_count: int
    error: Optional[str] = None


@dataclass
class OCRDocumentResult:
    full_text: str
    pages: List[OCRPageResult]
    avg_confidence: float
    typed_text_pct: float
    handwritten_text_pct: float
    total_processing_time_ms: int
    pages_processed: int
    pages_failed: int
    errors: List[str]


class ModalOCRClient:
    """Async client for Modal OCR service with retry logic and graceful degradation"""

    def __init__(
        self,
        app_name: Optional[str] = None,
        timeout: Optional[int] = None,
        enabled: Optional[bool] = None,
    ):
        self.app_name = app_name or settings.modal_app_name
        self.timeout = timeout or settings.modal_timeout
        self.enabled = enabled if enabled is not None else settings.modal_enabled

        if not MODAL_AVAILABLE:
            logger.warning("Modal SDK not installed - OCR disabled")
            self.enabled = self.available = False
            return

        try:
            self.stub = modal.App.lookup(self.app_name, create_if_missing=False)
            self.available = True
            logger.info(f"Modal OCR initialized: {self.app_name}")
        except Exception as e:
            logger.warning(f"Modal lookup failed: {e} - OCR disabled")
            self.available = self.enabled = False

    async def process_document_ocr(
        self,
        pdf_content: bytes,
        page_numbers: Optional[List[int]] = None,
        enable_handwriting: bool = True,
        request_id: Optional[str] = None,
    ) -> OCRDocumentResult:
        if not self.enabled or not self.available:
            raise ModalOCRError("Modal OCR is not available or disabled")

        start_time = time.time()
        logger.info("Starting OCR", extra={"request_id": request_id})

        try:
            from app.core.pdf_extractor import pdf_extractor

            if page_numbers:
                page_images_raw = [
                    pdf_extractor.render_page_for_ocr(pdf_content, n) for n in page_numbers
                ]
                # Filter out None values
                page_images = [img for img in page_images_raw if img is not None]
            else:
                page_images = pdf_extractor.render_all_pages(pdf_content)

            if not page_images:
                raise ModalOCRError("Failed to render any pages for OCR")

            # At this point all page_images are guaranteed non-None
            ocr_results = await self._call_ocr_batch(
                [img.image_base64 for img in page_images], enable_handwriting, request_id
            )

            page_results, errors = [], []
            for i, result_dict in enumerate(ocr_results):
                try:
                    pr = self._parse_page_result(result_dict)
                    page_results.append(pr)
                    if pr.error:
                        errors.append(f"Page {pr.page_num}: {pr.error}")
                except Exception as e:
                    errors.append(f"Page {i+1}: {e}")
                    page_results.append(OCRPageResult(i + 1, "", 0.0, 0.0, 0.0, 0, 0, str(e)))

            successful = [p for p in page_results if not p.error]
            if not successful:
                raise ModalOCRError(f"All pages failed: {errors}")

            result = OCRDocumentResult(
                full_text="\n\n".join(p.full_text for p in successful if p.full_text),
                pages=page_results,
                avg_confidence=sum(p.avg_confidence for p in successful) / len(successful),
                typed_text_pct=sum(p.typed_text_pct for p in successful) / len(successful),
                handwritten_text_pct=sum(p.handwritten_text_pct for p in successful)
                / len(successful),
                total_processing_time_ms=int((time.time() - start_time) * 1000),
                pages_processed=len(successful),
                pages_failed=len(page_results) - len(successful),
                errors=errors,
            )
            logger.info(
                f"OCR done: {result.pages_processed}/{len(page_results)}",
                extra={"request_id": request_id},
            )
            return result
        except ModalOCRError:
            raise
        except Exception as e:
            logger.error(f"OCR failed: {e}", extra={"request_id": request_id})
            raise ModalOCRError(f"OCR failed: {e}")

    async def process_page_ocr(
        self,
        page_image_base64: str,
        page_num: int,
        enable_handwriting: bool = True,
        request_id: Optional[str] = None,
    ) -> OCRPageResult:
        if not self.enabled or not self.available:
            raise ModalOCRError("Modal OCR not available")
        try:
            result = self._parse_page_result(
                await self._call_ocr_single_page(
                    page_image_base64, page_num, enable_handwriting, request_id
                )
            )
            logger.info(f"Page {page_num} done", extra={"request_id": request_id})
            return result
        except Exception as e:
            logger.error(f"Page {page_num} failed: {e}", extra={"request_id": request_id})
            raise ModalOCRError(f"Page OCR failed: {e}")

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=4, max=30),
        retry=retry_if_exception_type((Exception,)),
        reraise=True,
    )
    async def _call_ocr_batch(
        self, pages_base64: List[str], enable_handwriting: bool, request_id: Optional[str] = None
    ) -> List[Dict]:
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(self.stub.ocr_batch.remote, pages_base64, enable_handwriting),  # type: ignore[attr-defined]
                timeout=self.timeout,
            )
            if not isinstance(result, list):
                raise ModalOCRError(f"Invalid response type: {type(result)}")
            return result
        except asyncio.TimeoutError:
            raise ModalOCRError(f"Timeout after {self.timeout}s")

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((Exception,)),
        reraise=True,
    )
    async def _call_ocr_single_page(
        self,
        page_image_base64: str,
        page_num: int,
        enable_handwriting: bool,
        request_id: Optional[str] = None,
    ) -> Dict:
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(self.stub.ocr_single_page.remote, page_image_base64, page_num, enable_handwriting),  # type: ignore[attr-defined]
                timeout=30,
            )
            if not isinstance(result, dict):
                raise ModalOCRError(f"Invalid response: {type(result)}")
            return result
        except asyncio.TimeoutError:
            raise ModalOCRError("Timeout after 30s")

    def _parse_page_result(self, result_dict: Dict) -> OCRPageResult:
        required = [
            "page_num",
            "full_text",
            "avg_confidence",
            "typed_text_pct",
            "handwritten_text_pct",
            "processing_time_ms",
            "regions",
        ]
        missing = [f for f in required if f not in result_dict]
        if missing:
            raise ValueError(f"Missing required fields: {missing}")

        regions = result_dict.get("regions", [])
        return OCRPageResult(
            page_num=int(result_dict["page_num"]),
            full_text=str(result_dict["full_text"]),
            avg_confidence=float(result_dict["avg_confidence"]),
            typed_text_pct=float(result_dict["typed_text_pct"]),
            handwritten_text_pct=float(result_dict["handwritten_text_pct"]),
            processing_time_ms=int(result_dict["processing_time_ms"]),
            regions_count=len(regions) if isinstance(regions, list) else 0,
            error=result_dict.get("error"),
        )

    def is_available(self) -> bool:
        return self.enabled and self.available


class ModalOCRError(Exception):
    pass


modal_ocr_client = ModalOCRClient()
