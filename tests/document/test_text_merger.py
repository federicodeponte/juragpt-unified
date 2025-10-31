import pytest
from app.core.text_merger import TextMerger, TextSource, MergedDocument
from app.core.pdf_extractor import PageText
from app.services.modal_client import OCRPageResult, OCRDocumentResult


@pytest.fixture
def merger():
    return TextMerger(quality_threshold=0.7, ocr_confidence_threshold=0.75)


@pytest.fixture
def embedded_pages():
    return [
        PageText(1, "High quality page 1", 20, 4, None, 0.95),
        PageText(2, "Poor quality page 2", 20, 4, None, 0.4),
        PageText(3, "", 0, 0, None, 0.0),
    ]


@pytest.fixture
def ocr_result():
    return OCRDocumentResult(
        full_text="OCR page 1\n\nOCR page 2\n\nOCR page 3",
        pages=[
            OCRPageResult(1, "OCR page 1", 0.92, 100.0, 0.0, 1500, 5),
            OCRPageResult(2, "OCR page 2", 0.88, 80.0, 20.0, 2000, 8),
            OCRPageResult(3, "OCR page 3", 0.85, 70.0, 30.0, 1800, 6),
        ],
        avg_confidence=0.88,
        typed_text_pct=83.3,
        handwritten_text_pct=16.7,
        total_processing_time_ms=5300,
        pages_processed=3,
        pages_failed=0,
        errors=[],
    )


def test_excellent_quality_uses_embedded(merger, embedded_pages, ocr_result):
    result = merger.merge_document(embedded_pages, ocr_result, "excellent")
    assert result.pages[0].source == TextSource.EMBEDDED
    assert result.pages[0].text == "High quality page 1"
    assert result.pages[0].confidence >= 0.9


def test_poor_quality_high_ocr_uses_ocr(merger, embedded_pages, ocr_result):
    result = merger.merge_document(embedded_pages, ocr_result, "poor")
    assert result.pages[1].source == TextSource.OCR
    assert result.pages[1].text == "OCR page 2"
    assert result.pages[1].confidence == 0.88


def test_poor_quality_low_ocr_uses_fallback(merger, embedded_pages):
    low_conf_ocr = OCRDocumentResult(
        "Low conf",
        [
            OCRPageResult(1, "Low conf", 0.5, 100.0, 0.0, 1000, 2),
            OCRPageResult(2, "Low conf", 0.6, 100.0, 0.0, 1000, 2),
        ],
        0.55,
        100.0,
        0.0,
        2000,
        2,
        0,
        [],
    )
    result = merger.merge_document(embedded_pages[:2], low_conf_ocr, "poor")
    assert result.pages[1].source == TextSource.FALLBACK


def test_no_embedded_uses_ocr(merger, embedded_pages, ocr_result):
    result = merger.merge_document(embedded_pages, ocr_result, "none")
    assert result.pages[2].source == TextSource.OCR
    assert result.pages[2].text == "OCR page 3"


def test_no_ocr_uses_embedded(merger, embedded_pages):
    empty_ocr = OCRDocumentResult("", [], 0.0, 0.0, 0.0, 0, 0, 0, [])
    result = merger.merge_document(embedded_pages[:1], empty_ocr, "good")
    assert result.pages[0].source == TextSource.EMBEDDED


def test_mixed_document_decisions(merger, embedded_pages, ocr_result):
    result = merger.merge_document(embedded_pages, ocr_result, "poor")
    assert result.stats["ocr"] >= 1
    assert len(result.pages) == 3


def test_full_text_concatenation(merger, embedded_pages, ocr_result):
    result = merger.merge_document(embedded_pages, ocr_result, "excellent")
    assert "High quality page 1" in result.full_text
    assert result.full_text.count("\n\n") >= 1


def test_stats_calculation(merger, embedded_pages, ocr_result):
    result = merger.merge_document(embedded_pages, ocr_result, "excellent")
    assert sum(result.stats.values()) == 3
    assert "embedded" in result.stats and "ocr" in result.stats


def test_avg_confidence(merger, embedded_pages, ocr_result):
    result = merger.merge_document(embedded_pages, ocr_result, "good")
    assert 0.0 <= result.avg_confidence <= 1.0


def test_merge_report(merger, embedded_pages, ocr_result):
    merged = merger.merge_document(embedded_pages, ocr_result, "poor")
    report = merger.generate_merge_report(merged)
    assert report["total_pages"] == 3
    assert "source_distribution" in report
    assert len(report["pages_detail"]) == 3
    assert all("reason" in p for p in report["pages_detail"])
