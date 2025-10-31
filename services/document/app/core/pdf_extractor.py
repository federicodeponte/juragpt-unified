"""
ABOUTME: PDF text extraction with PyMuPDF including embedded text + bbox
ABOUTME: Prepares pages for OCR processing when needed
"""

import base64
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import fitz  # PyMuPDF

from app.utils.logging import logger


@dataclass
class PageText:
    """Text extracted from a single page"""

    page_num: int
    text: str
    char_count: int
    word_count: int
    bbox: Optional[Tuple[float, float, float, float]] = None
    confidence: float = 1.0  # Embedded text has 100% confidence


@dataclass
class PageImage:
    """Rendered page image for OCR"""

    page_num: int
    image_base64: str
    width: int
    height: int
    dpi: int = 150


class PDFExtractor:
    """
    Extract text and images from PDFs using PyMuPDF
    Supports both embedded text and page rendering
    """

    def __init__(self, dpi: int = 150):
        """
        Initialize PDF extractor

        Args:
            dpi: Resolution for page rendering (default 150, higher = better quality)
        """
        self.dpi = dpi

    def extract_embedded_text(self, pdf_content: bytes) -> List[PageText]:
        """
        Extract embedded text layer from PDF with positions

        Args:
            pdf_content: PDF file bytes

        Returns:
            List of PageText objects, one per page
        """
        pages = []

        try:
            doc = fitz.open(stream=pdf_content, filetype="pdf")

            for page_num in range(len(doc)):
                page = doc[page_num]

                # Extract text
                text = page.get_text()

                # Get bounding box of all text on page
                bbox = None
                text_instances = page.get_text("dict")
                if text_instances and "blocks" in text_instances:
                    # Calculate overall bbox from all text blocks
                    bboxes = [
                        block["bbox"] for block in text_instances["blocks"] if "bbox" in block
                    ]
                    if bboxes:
                        # Get min/max coords
                        x0 = min(b[0] for b in bboxes)
                        y0 = min(b[1] for b in bboxes)
                        x1 = max(b[2] for b in bboxes)
                        y1 = max(b[3] for b in bboxes)
                        bbox = (x0, y0, x1, y1)

                pages.append(
                    PageText(
                        page_num=page_num + 1,  # 1-indexed
                        text=text.strip(),
                        char_count=len(text),
                        word_count=len(text.split()),
                        bbox=bbox,
                        confidence=1.0,  # Embedded text is 100% accurate
                    )
                )

            doc.close()

            logger.info(f"Extracted embedded text from {len(pages)} pages")
            return pages

        except Exception as e:
            logger.error(f"Embedded text extraction failed: {str(e)}")
            return []

    def render_page_for_ocr(self, pdf_content: bytes, page_num: int) -> Optional[PageImage]:
        """
        Render a single PDF page as image for OCR processing

        Args:
            pdf_content: PDF file bytes
            page_num: Page number (1-indexed)

        Returns:
            PageImage with base64-encoded PNG, or None on error
        """
        try:
            doc = fitz.open(stream=pdf_content, filetype="pdf")

            if page_num < 1 or page_num > len(doc):
                logger.error(f"Invalid page number: {page_num}")
                return None

            page = doc[page_num - 1]  # Convert to 0-indexed

            # Render page to image
            # Higher DPI = better quality but larger file
            zoom = self.dpi / 72  # 72 DPI is PDF standard
            mat = fitz.Matrix(zoom, zoom)
            pix = page.get_pixmap(matrix=mat)

            # Convert to PNG bytes
            img_bytes = pix.tobytes("png")

            # Base64 encode for transmission
            img_base64 = base64.b64encode(img_bytes).decode("utf-8")

            doc.close()

            return PageImage(
                page_num=page_num,
                image_base64=img_base64,
                width=pix.width,
                height=pix.height,
                dpi=self.dpi,
            )

        except Exception as e:
            logger.error(f"Page rendering failed for page {page_num}: {str(e)}")
            return None

    def render_all_pages(self, pdf_content: bytes) -> List[PageImage]:
        """
        Render all PDF pages as images

        Args:
            pdf_content: PDF file bytes

        Returns:
            List of PageImage objects
        """
        images = []

        try:
            doc = fitz.open(stream=pdf_content, filetype="pdf")
            total_pages = len(doc)

            for page_num in range(1, total_pages + 1):
                page_image = self.render_page_for_ocr(pdf_content, page_num)
                if page_image:
                    images.append(page_image)

            doc.close()

            logger.info(f"Rendered {len(images)}/{total_pages} pages")
            return images

        except Exception as e:
            logger.error(f"Batch rendering failed: {str(e)}")
            return []

    def extract_metadata(self, pdf_content: bytes) -> Dict:
        """
        Extract PDF metadata

        Args:
            pdf_content: PDF file bytes

        Returns:
            Dict with metadata (author, title, creation date, etc.)
        """
        try:
            doc = fitz.open(stream=pdf_content, filetype="pdf")
            metadata = doc.metadata

            # Clean up metadata (remove None values)
            cleaned = {k: v for k, v in metadata.items() if v is not None and v.strip()}

            doc.close()
            return cleaned

        except Exception as e:
            logger.error(f"Metadata extraction failed: {str(e)}")
            return {}

    def check_text_layer_quality(self, pdf_content: bytes) -> Tuple[float, bool]:
        """
        Quick check of text layer quality

        Args:
            pdf_content: PDF file bytes

        Returns:
            Tuple of (text_coverage_percentage, needs_ocr)
        """
        try:
            doc = fitz.open(stream=pdf_content, filetype="pdf")

            total_pages = len(doc)
            pages_with_text = 0

            for page_num in range(total_pages):
                page = doc[page_num]
                text = page.get_text()

                # Count as having text if > 10 characters
                if text and len(text.strip()) > 10:
                    pages_with_text += 1

            doc.close()

            coverage = (pages_with_text / total_pages * 100) if total_pages > 0 else 0
            needs_ocr = coverage < 70  # Less than 70% coverage needs OCR

            return coverage, needs_ocr

        except Exception as e:
            logger.error(f"Text quality check failed: {str(e)}")
            return 0.0, True  # Assume needs OCR on error


# Global instance
pdf_extractor = PDFExtractor()
