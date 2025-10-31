"""
ABOUTME: Multi-format file detection and analysis for legal documents
ABOUTME: Detects PDF (with/without text), DOCX, ODT, EML, ZIP and checks quality
"""

import hashlib
from enum import Enum
from pathlib import Path
from typing import Dict, Optional

import fitz  # PyMuPDF
import magic
from langdetect import LangDetectException, detect

from app.utils.logging import logger


class FileType(str, Enum):
    """Supported document file types"""

    PDF = "pdf"
    DOCX = "docx"
    ODT = "odt"
    EML = "eml"
    ZIP = "zip"
    UNKNOWN = "unknown"


class TextLayerQuality(str, Enum):
    """Quality of embedded text layer in PDFs"""

    EXCELLENT = "excellent"  # >90% pages with text
    GOOD = "good"  # 70-90% pages with text
    POOR = "poor"  # <70% pages with text
    NONE = "none"  # No text layer
    UNKNOWN = "unknown"  # Unable to determine


class FileDetector:
    """
    Detect file type, text layer presence, and quality metrics
    Determines optimal extraction strategy
    """

    def __init__(self):
        self.magic = magic.Magic(mime=True)

    def detect_file_type(self, file_content: bytes, filename: str) -> FileType:
        """
        Detect file type from content and filename

        Args:
            file_content: Raw file bytes
            filename: Original filename

        Returns:
            FileType enum
        """
        # Try MIME type detection
        mime_type = self.magic.from_buffer(file_content)

        # Map MIME types to our FileType
        mime_mapping = {
            "application/pdf": FileType.PDF,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": FileType.DOCX,
            "application/vnd.oasis.opendocument.text": FileType.ODT,
            "message/rfc822": FileType.EML,
            "application/zip": FileType.ZIP,
            "application/x-zip-compressed": FileType.ZIP,
        }

        detected_type = mime_mapping.get(mime_type, FileType.UNKNOWN)

        # Fallback to extension if MIME detection fails
        if detected_type == FileType.UNKNOWN:
            extension = Path(filename).suffix.lower().lstrip(".")
            extension_mapping = {
                "pdf": FileType.PDF,
                "docx": FileType.DOCX,
                "odt": FileType.ODT,
                "eml": FileType.EML,
                "msg": FileType.EML,
                "zip": FileType.ZIP,
            }
            detected_type = extension_mapping.get(extension, FileType.UNKNOWN)

        logger.info(f"Detected file type: {detected_type.value} for {filename}")
        return detected_type

    def analyze_pdf(self, file_content: bytes) -> Dict:
        """
        Analyze PDF text layer quality and characteristics

        Args:
            file_content: PDF file bytes

        Returns:
            Dict with analysis results
        """
        try:
            doc = fitz.open(stream=file_content, filetype="pdf")

            total_pages = len(doc)
            pages_with_text = 0
            total_chars = 0
            has_images = False

            for page_num in range(total_pages):
                page = doc[page_num]

                # Check for text
                text = page.get_text()
                if text and len(text.strip()) > 10:  # At least 10 chars
                    pages_with_text += 1
                    total_chars += len(text)

                # Check for images
                if not has_images:
                    image_list = page.get_images()
                    if image_list:
                        has_images = True

            doc.close()

            # Calculate text coverage percentage
            text_coverage = (pages_with_text / total_pages * 100) if total_pages > 0 else 0

            # Determine text layer quality
            if text_coverage >= 90:
                quality = TextLayerQuality.EXCELLENT
            elif text_coverage >= 70:
                quality = TextLayerQuality.GOOD
            elif text_coverage > 0:
                quality = TextLayerQuality.POOR
            else:
                quality = TextLayerQuality.NONE

            return {
                "total_pages": total_pages,
                "pages_with_text": pages_with_text,
                "text_coverage_pct": round(text_coverage, 2),
                "text_layer_quality": quality.value,
                "total_chars": total_chars,
                "has_images": has_images,
                "needs_ocr": quality in [TextLayerQuality.POOR, TextLayerQuality.NONE],
            }

        except Exception as e:
            logger.error(f"PDF analysis failed: {str(e)}")
            return {
                "total_pages": 0,
                "text_layer_quality": TextLayerQuality.UNKNOWN,
                "needs_ocr": True,
                "error": str(e),
            }

    def detect_language(self, text: str) -> Optional[str]:
        """
        Detect primary language of text

        Args:
            text: Sample text (first 500 chars sufficient)

        Returns:
            ISO language code (e.g., 'de', 'en') or None
        """
        if not text or len(text.strip()) < 20:
            return None

        try:
            # Use first 500 chars for performance
            sample = text[:500]
            lang = detect(sample)
            return lang
        except LangDetectException:
            logger.warning("Language detection failed")
            return None

    def compute_file_hash(self, file_content: bytes) -> str:
        """
        Compute SHA-256 hash of file content
        For deduplication and versioning

        Args:
            file_content: Raw file bytes

        Returns:
            Hex-encoded SHA-256 hash
        """
        return hashlib.sha256(file_content).hexdigest()

    def analyze_file(self, file_content: bytes, filename: str) -> Dict:
        """
        Complete file analysis pipeline

        Args:
            file_content: Raw file bytes
            filename: Original filename

        Returns:
            Comprehensive analysis dict
        """
        file_hash = self.compute_file_hash(file_content)
        file_type = self.detect_file_type(file_content, filename)

        analysis = {
            "filename": filename,
            "file_hash": file_hash,
            "file_type": file_type.value,
            "file_size_bytes": len(file_content),
        }

        # PDF-specific analysis
        if file_type == FileType.PDF:
            pdf_analysis = self.analyze_pdf(file_content)
            analysis.update(pdf_analysis)

        return analysis


# Global instance
file_detector = FileDetector()
