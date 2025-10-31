"""
ABOUTME: Intelligent merging of embedded PDF text and OCR results
ABOUTME: Page-level decision making based on text quality and OCR confidence
"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional

from app.core.file_detector import TextLayerQuality
from app.core.pdf_extractor import PageText
from app.services.modal_client import OCRDocumentResult, OCRPageResult
from app.utils.logging import logger


class TextSource(str, Enum):
    EMBEDDED = "embedded"
    OCR = "ocr"
    HYBRID = "hybrid"
    FALLBACK = "fallback"


@dataclass
class MergedPage:
    page_num: int
    text: str
    source: TextSource
    confidence: float
    reason: str


@dataclass
class MergedDocument:
    full_text: str
    pages: List[MergedPage]
    stats: Dict[str, int]
    avg_confidence: float


class TextMerger:
    """Merges embedded PDF text with OCR using page-level quality decisions"""

    def __init__(self, quality_threshold: float = 0.7, ocr_confidence_threshold: float = 0.75):
        self.quality_threshold = quality_threshold
        self.ocr_confidence_threshold = ocr_confidence_threshold

    def merge_document(
        self,
        embedded_pages: List[PageText],
        ocr_result: OCRDocumentResult,
        text_layer_quality: str,
        request_id: Optional[str] = None,
    ) -> MergedDocument:
        """Merge embedded + OCR text page-by-page based on quality"""
        logger.info(
            f"Merging {len(embedded_pages)} embedded with {len(ocr_result.pages)} OCR pages",
            extra={"request_id": request_id},
        )

        ocr_by_page = {p.page_num: p for p in ocr_result.pages if not p.error}

        merged_pages = []
        stats = {"embedded": 0, "ocr": 0, "hybrid": 0, "fallback": 0}

        for emb_page in embedded_pages:
            merged = self._merge_page(
                emb_page, ocr_by_page.get(emb_page.page_num), text_layer_quality, request_id
            )
            merged_pages.append(merged)
            stats[merged.source.value] += 1

        full_text = "\n\n".join(p.text for p in merged_pages if p.text)
        avg_conf = (
            sum(p.confidence for p in merged_pages) / len(merged_pages) if merged_pages else 0.0
        )

        logger.info(
            f"Merge complete: {stats}, conf={avg_conf:.2f}", extra={"request_id": request_id}
        )

        return MergedDocument(
            full_text=full_text, pages=merged_pages, stats=stats, avg_confidence=avg_conf
        )

    def _merge_page(
        self,
        embedded: PageText,
        ocr: Optional[OCRPageResult],
        overall_quality: str,
        request_id: Optional[str] = None,
    ) -> MergedPage:
        """Decide which text source to use for a single page based on quality"""
        if not ocr:
            return MergedPage(
                page_num=embedded.page_num,
                text=embedded.text,
                source=TextSource.EMBEDDED,
                confidence=0.9,
                reason="No OCR result available",
            )

        try:
            quality = TextLayerQuality(overall_quality.lower()) if overall_quality else None
        except ValueError:
            return MergedPage(
                page_num=embedded.page_num,
                text=embedded.text,
                source=TextSource.EMBEDDED,
                confidence=0.8,
                reason=f"Unknown quality '{overall_quality}' - using embedded",
            )

        if quality in [TextLayerQuality.EXCELLENT, TextLayerQuality.GOOD]:
            return MergedPage(
                page_num=embedded.page_num,
                text=embedded.text,
                source=TextSource.EMBEDDED,
                confidence=0.95 if quality == TextLayerQuality.EXCELLENT else 0.85,
                reason=f"Embedded quality: {quality.value}",
            )

        elif quality == TextLayerQuality.NONE:
            return MergedPage(
                page_num=embedded.page_num,
                text=ocr.full_text,
                source=TextSource.OCR,
                confidence=ocr.avg_confidence,
                reason="No embedded text",
            )

        elif quality == TextLayerQuality.POOR:
            if ocr.avg_confidence >= self.ocr_confidence_threshold:
                return MergedPage(
                    page_num=embedded.page_num,
                    text=ocr.full_text,
                    source=TextSource.OCR,
                    confidence=ocr.avg_confidence,
                    reason=f"OCR conf ({ocr.avg_confidence:.2f}) > threshold",
                )
            else:
                return MergedPage(
                    page_num=embedded.page_num,
                    text=embedded.text,
                    source=TextSource.FALLBACK,
                    confidence=0.6,
                    reason=f"Low OCR conf ({ocr.avg_confidence:.2f})",
                )

        else:
            return MergedPage(
                page_num=embedded.page_num,
                text=embedded.text,
                source=TextSource.EMBEDDED,
                confidence=0.7,
                reason="Unknown quality",
            )

    def generate_merge_report(self, merged: MergedDocument) -> Dict:
        """Generate audit report for merge decisions"""
        return {
            "total_pages": len(merged.pages),
            "avg_confidence": merged.avg_confidence,
            "source_distribution": merged.stats,
            "pages_detail": [
                {
                    "page": p.page_num,
                    "source": p.source.value,
                    "confidence": p.confidence,
                    "reason": p.reason,
                }
                for p in merged.pages
            ],
        }


# Global instance
text_merger = TextMerger()
