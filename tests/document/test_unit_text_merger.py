"""Unit tests for text merger module"""

import pytest
from app.core.text_merger import TextMerger, TextSource, MergedPage, MergedDocument
from app.core.pdf_extractor import PageText
from app.services.modal_client import OCRDocumentResult, OCRPageResult
from app.core.file_detector import TextLayerQuality


class TestTextSource:
    """Test TextSource enum"""

    def test_text_source_values(self):
        assert TextSource.EMBEDDED == "embedded"
        assert TextSource.OCR == "ocr"
        assert TextSource.HYBRID == "hybrid"
        assert TextSource.FALLBACK == "fallback"

    def test_text_source_enum_members(self):
        assert len(TextSource) == 4
        assert TextSource.EMBEDDED in TextSource
        assert TextSource.OCR in TextSource


class TestMergedPage:
    """Test MergedPage dataclass"""

    def test_merged_page_creation(self):
        page = MergedPage(
            page_num=1,
            text="Test content",
            source=TextSource.EMBEDDED,
            confidence=0.95,
            reason="High quality",
        )
        assert page.page_num == 1
        assert page.text == "Test content"
        assert page.source == TextSource.EMBEDDED
        assert page.confidence == 0.95
        assert page.reason == "High quality"

    def test_merged_page_source_types(self):
        for source in TextSource:
            page = MergedPage(1, "text", source, 0.9, "test")
            assert page.source == source


class TestMergedDocument:
    """Test MergedDocument dataclass"""

    def test_merged_document_creation(self):
        pages = [
            MergedPage(1, "Page 1", TextSource.EMBEDDED, 0.95, "High quality"),
            MergedPage(2, "Page 2", TextSource.OCR, 0.88, "OCR used"),
        ]
        doc = MergedDocument(
            full_text="Page 1\n\nPage 2",
            pages=pages,
            stats={"embedded": 1, "ocr": 1},
            avg_confidence=0.915,
        )

        assert doc.full_text == "Page 1\n\nPage 2"
        assert len(doc.pages) == 2
        assert doc.stats["embedded"] == 1
        assert doc.stats["ocr"] == 1
        assert doc.avg_confidence == 0.915

    def test_merged_document_empty_pages(self):
        doc = MergedDocument("", [], {}, 0.0)
        assert doc.full_text == ""
        assert len(doc.pages) == 0
        assert doc.avg_confidence == 0.0


class TestTextMerger:
    """Test TextMerger class"""

    @pytest.fixture
    def merger(self):
        return TextMerger(quality_threshold=0.7, ocr_confidence_threshold=0.75)

    @pytest.fixture
    def high_quality_embedded(self):
        return [
            PageText(1, "High quality page 1", 100, 20, None, 0.95),
            PageText(2, "High quality page 2", 100, 20, None, 0.93),
        ]

    @pytest.fixture
    def poor_quality_embedded(self):
        return [
            PageText(1, "Poor quality page 1", 50, 10, None, 0.35),
            PageText(2, "Poor quality page 2", 40, 8, None, 0.30),
        ]

    @pytest.fixture
    def high_confidence_ocr(self):
        return OCRDocumentResult(
            full_text="OCR page 1\n\nOCR page 2",
            pages=[
                OCRPageResult(1, "OCR page 1", 0.92, 100.0, 0.0, 1500, 5),
                OCRPageResult(2, "OCR page 2", 0.90, 100.0, 0.0, 1500, 5),
            ],
            avg_confidence=0.91,
            typed_text_pct=100.0,
            handwritten_text_pct=0.0,
            total_processing_time_ms=3000,
            pages_processed=2,
            pages_failed=0,
            errors=[],
        )

    def test_merger_initialization(self):
        merger = TextMerger(quality_threshold=0.8, ocr_confidence_threshold=0.85)
        assert merger.quality_threshold == 0.8
        assert merger.ocr_confidence_threshold == 0.85

    def test_merger_default_thresholds(self):
        merger = TextMerger()
        assert merger.quality_threshold == 0.7
        assert merger.ocr_confidence_threshold == 0.75

    def test_excellent_quality_uses_embedded(
        self, merger, high_quality_embedded, high_confidence_ocr
    ):
        result = merger.merge_document(high_quality_embedded, high_confidence_ocr, "excellent")

        assert len(result.pages) == 2
        assert all(p.source == TextSource.EMBEDDED for p in result.pages)
        assert result.stats["embedded"] == 2
        assert result.stats["ocr"] == 0
        assert result.avg_confidence > 0.9

    def test_good_quality_uses_embedded(self, merger, high_quality_embedded, high_confidence_ocr):
        result = merger.merge_document(high_quality_embedded, high_confidence_ocr, "good")

        assert all(p.source == TextSource.EMBEDDED for p in result.pages)
        assert result.stats["embedded"] == 2

    def test_poor_quality_high_ocr_uses_ocr(
        self, merger, poor_quality_embedded, high_confidence_ocr
    ):
        result = merger.merge_document(poor_quality_embedded, high_confidence_ocr, "poor")

        assert all(p.source == TextSource.OCR for p in result.pages)
        assert result.stats["ocr"] == 2
        assert result.stats["embedded"] == 0

    def test_poor_quality_low_ocr_uses_fallback(self, merger, poor_quality_embedded):
        low_ocr = OCRDocumentResult(
            "Low confidence",
            [
                OCRPageResult(1, "Low conf 1", 0.5, 100.0, 0.0, 1000, 2),
                OCRPageResult(2, "Low conf 2", 0.6, 100.0, 0.0, 1000, 2),
            ],
            0.55,
            100.0,
            0.0,
            2000,
            2,
            0,
            [],
        )

        result = merger.merge_document(poor_quality_embedded, low_ocr, "poor")

        assert all(p.source == TextSource.FALLBACK for p in result.pages)
        assert result.stats["fallback"] == 2

    def test_none_quality_uses_ocr(self, merger, high_confidence_ocr):
        empty_embedded = [PageText(1, "", 0, 0, None, 0.0)]
        result = merger.merge_document(empty_embedded, high_confidence_ocr, "none")

        assert result.pages[0].source == TextSource.OCR
        assert result.stats["ocr"] >= 1

    def test_no_ocr_result_uses_embedded(self, merger, high_quality_embedded):
        empty_ocr = OCRDocumentResult("", [], 0.0, 0.0, 0.0, 0, 0, 0, [])
        result = merger.merge_document(high_quality_embedded, empty_ocr, "excellent")

        assert all(p.source == TextSource.EMBEDDED for p in result.pages)
        assert "No OCR result available" in result.pages[0].reason

    def test_full_text_concatenation(self, merger, high_quality_embedded, high_confidence_ocr):
        result = merger.merge_document(high_quality_embedded, high_confidence_ocr, "excellent")

        assert "High quality page 1" in result.full_text
        assert "High quality page 2" in result.full_text
        assert "\n\n" in result.full_text

    def test_average_confidence_calculation(
        self, merger, high_quality_embedded, high_confidence_ocr
    ):
        result = merger.merge_document(high_quality_embedded, high_confidence_ocr, "excellent")

        assert 0.0 <= result.avg_confidence <= 1.0
        # With 2 pages at ~0.95 confidence each
        assert result.avg_confidence > 0.9

    def test_stats_all_sources_counted(self, merger):
        # Mix of page qualities to trigger different sources
        mixed_embedded = [
            PageText(1, "Good page", 100, 20, None, 0.95),  # Will use embedded (excellent quality)
            PageText(2, "", 0, 0, None, 0.0),  # Will use OCR (none quality)
        ]

        mixed_ocr = OCRDocumentResult(
            "OCR 1\n\nOCR 2",
            [
                OCRPageResult(1, "OCR 1", 0.92, 100.0, 0.0, 1500, 5),
                OCRPageResult(2, "OCR 2", 0.90, 100.0, 0.0, 1500, 5),
            ],
            0.91,
            100.0,
            0.0,
            3000,
            2,
            0,
            [],
        )

        result = merger.merge_document(mixed_embedded, mixed_ocr, "excellent")

        total_pages = sum(result.stats.values())
        assert total_pages == 2

    def test_generate_merge_report(self, merger, high_quality_embedded, high_confidence_ocr):
        merged = merger.merge_document(high_quality_embedded, high_confidence_ocr, "excellent")
        report = merger.generate_merge_report(merged)

        assert "total_pages" in report
        assert report["total_pages"] == 2
        assert "avg_confidence" in report
        assert "source_distribution" in report
        assert "pages_detail" in report
        assert len(report["pages_detail"]) == 2

        # Check page detail structure
        page_detail = report["pages_detail"][0]
        assert "page" in page_detail
        assert "source" in page_detail
        assert "confidence" in page_detail
        assert "reason" in page_detail

    def test_request_id_logging(self, merger, high_quality_embedded, high_confidence_ocr):
        # Should not raise error with request_id
        result = merger.merge_document(
            high_quality_embedded, high_confidence_ocr, "excellent", request_id="test-request-123"
        )
        assert result is not None

    def test_unknown_quality_defaults_to_embedded(
        self, merger, high_quality_embedded, high_confidence_ocr
    ):
        result = merger.merge_document(high_quality_embedded, high_confidence_ocr, "unknown")

        # Should default to embedded as safest option
        assert result.pages[0].source == TextSource.EMBEDDED
        assert "Unknown quality" in result.pages[0].reason

    def test_empty_document(self, merger):
        empty_embedded = []
        empty_ocr = OCRDocumentResult("", [], 0.0, 0.0, 0.0, 0, 0, 0, [])

        result = merger.merge_document(empty_embedded, empty_ocr, "excellent")

        assert result.full_text == ""
        assert len(result.pages) == 0
        assert result.avg_confidence == 0.0

    def test_single_page_document(self, merger):
        single_page = [PageText(1, "Single page content", 100, 20, None, 0.95)]
        single_ocr = OCRDocumentResult(
            "OCR single",
            [OCRPageResult(1, "OCR single", 0.92, 100.0, 0.0, 1500, 5)],
            0.92,
            100.0,
            0.0,
            1500,
            1,
            0,
            [],
        )

        result = merger.merge_document(single_page, single_ocr, "excellent")

        assert len(result.pages) == 1
        assert result.avg_confidence > 0.0
        assert result.full_text == "Single page content"

    def test_large_document_100_pages(self, merger):
        large_embedded = [PageText(i, f"Page {i}", 100, 20, None, 0.9) for i in range(1, 101)]
        large_ocr = OCRDocumentResult(
            "\n\n".join([f"OCR {i}" for i in range(1, 101)]),
            [OCRPageResult(i, f"OCR {i}", 0.88, 100.0, 0.0, 1500, 5) for i in range(1, 101)],
            0.88,
            100.0,
            0.0,
            150000,
            100,
            0,
            [],
        )

        result = merger.merge_document(large_embedded, large_ocr, "excellent")

        assert len(result.pages) == 100
        assert sum(result.stats.values()) == 100
        assert 0.0 < result.avg_confidence <= 1.0


class TestGlobalTextMerger:
    """Test global text_merger instance"""

    def test_global_instance_exists(self):
        from app.core.text_merger import text_merger

        assert text_merger is not None
        assert isinstance(text_merger, TextMerger)

    def test_global_instance_default_config(self):
        from app.core.text_merger import text_merger

        assert text_merger.quality_threshold == 0.7
        assert text_merger.ocr_confidence_threshold == 0.75
