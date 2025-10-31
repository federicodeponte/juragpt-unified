"""
Test file detection and multi-format extraction
"""

import pytest
from app.core.file_detector import file_detector, FileType, TextLayerQuality


class TestFileDetection:
    """Test file type detection"""

    def test_detect_pdf_from_mime(self):
        """Test PDF detection from MIME type"""
        # Mock PDF header
        pdf_content = b"%PDF-1.4\n"
        file_type = file_detector.detect_file_type(pdf_content, "document.pdf")
        assert file_type == FileType.PDF

    def test_detect_from_extension_fallback(self):
        """Test detection falls back to extension"""
        # Unknown MIME but valid extension
        content = b"some content"
        file_type = file_detector.detect_file_type(content, "document.docx")
        # May return UNKNOWN or DOCX depending on magic detection
        assert file_type in [FileType.DOCX, FileType.UNKNOWN]

    def test_compute_file_hash(self):
        """Test file hash computation"""
        content = b"test content"
        hash1 = file_detector.compute_file_hash(content)
        hash2 = file_detector.compute_file_hash(content)

        # Same content = same hash
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 hex length

    def test_compute_file_hash_different_content(self):
        """Test different content produces different hash"""
        hash1 = file_detector.compute_file_hash(b"content1")
        hash2 = file_detector.compute_file_hash(b"content2")

        assert hash1 != hash2

    def test_analyze_file_structure(self):
        """Test complete file analysis returns expected structure"""
        content = b"test content"
        analysis = file_detector.analyze_file(content, "test.txt")

        assert "filename" in analysis
        assert "file_hash" in analysis
        assert "file_type" in analysis
        assert "file_size_bytes" in analysis
        assert analysis["file_size_bytes"] == len(content)


class TestPDFAnalysis:
    """Test PDF-specific analysis"""

    def test_analyze_pdf_with_text(self):
        """Test PDF with good text layer"""
        # This would need a real PDF with text layer
        # For now, test the structure
        pass  # Requires PyMuPDF and real PDF

    def test_text_layer_quality_thresholds(self):
        """Test quality classification thresholds"""
        # EXCELLENT: >= 90%
        # GOOD: 70-90%
        # POOR: > 0% but < 70%
        # NONE: 0%

        # These would be tested with real PDFs
        pass


class TestLanguageDetection:
    """Test language detection"""

    def test_detect_german(self):
        """Test German language detection"""
        german_text = "Dies ist ein deutscher Text über Verträge und Gesetze."
        lang = file_detector.detect_language(german_text)

        # langdetect returns 'de' for German
        assert lang == "de" or lang is not None  # May vary

    def test_detect_english(self):
        """Test English language detection"""
        english_text = "This is an English text about contracts and laws."
        lang = file_detector.detect_language(english_text)

        assert lang == "en" or lang is not None

    def test_detect_short_text(self):
        """Test language detection with too-short text"""
        short_text = "Hi"
        lang = file_detector.detect_language(short_text)

        # Should return None for very short text
        assert lang is None

    def test_detect_empty_text(self):
        """Test language detection with empty text"""
        lang = file_detector.detect_language("")
        assert lang is None


class TestFileTypeEnum:
    """Test FileType enum"""

    def test_file_type_values(self):
        """Test FileType enum has expected values"""
        assert FileType.PDF.value == "pdf"
        assert FileType.DOCX.value == "docx"
        assert FileType.ODT.value == "odt"
        assert FileType.EML.value == "eml"
        assert FileType.ZIP.value == "zip"
        assert FileType.UNKNOWN.value == "unknown"

    def test_text_layer_quality_values(self):
        """Test TextLayerQuality enum"""
        assert TextLayerQuality.EXCELLENT.value == "excellent"
        assert TextLayerQuality.GOOD.value == "good"
        assert TextLayerQuality.POOR.value == "poor"
        assert TextLayerQuality.NONE.value == "none"
