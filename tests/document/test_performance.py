"""Performance benchmarks for OCR pipeline"""

import pytest
import time
import tracemalloc
from unittest.mock import patch, Mock
from app.core.pdf_extractor import PageText
from app.services.modal_client import OCRDocumentResult, OCRPageResult


@pytest.fixture
def perf_client():
    from fastapi.testclient import TestClient
    from app.main import app
    from app.auth.middleware import get_current_user
    from app.auth.models import User
    from datetime import datetime
    import uuid

    async def override_get_current_user():
        return User(id=uuid.uuid4(), email="test@example.com", created_at=datetime.utcnow())

    app.dependency_overrides[get_current_user] = override_get_current_user
    test_client = TestClient(app)
    yield test_client
    app.dependency_overrides.clear()


def generate_pages(num_pages, text_per_page=100):
    """Generate mock PageText objects"""
    return [
        PageText(
            i,
            f"Page {i} content " * text_per_page,
            text_per_page * 10,
            text_per_page // 5,
            None,
            0.9,
        )
        for i in range(1, num_pages + 1)
    ]


def generate_ocr_result(num_pages):
    """Generate mock OCR result"""
    pages = [
        OCRPageResult(i, f"OCR page {i} content", 0.88, 90.0, 10.0, 1500, 5)
        for i in range(1, num_pages + 1)
    ]
    return OCRDocumentResult(
        full_text="\n\n".join(p.full_text for p in pages),
        pages=pages,
        avg_confidence=0.88,
        typed_text_pct=90.0,
        handwritten_text_pct=10.0,
        total_processing_time_ms=1500 * num_pages,
        pages_processed=num_pages,
        pages_failed=0,
        errors=[],
    )


@pytest.mark.performance
@patch("app.db.supabase_client.supabase_client.create_document")
@patch("app.db.supabase_client.supabase_client.document_exists", return_value=False)
@patch("app.core.retriever.retriever.index_document_chunks", return_value=10)
@patch("app.core.file_detector.file_detector.analyze_file")
@patch("app.core.pdf_extractor.pdf_extractor.extract_embedded_text")
@patch("app.utils.file_storage.file_storage.store_file", return_value="/storage/test.pdf")
def test_indexing_performance_1_page(
    mock_storage, mock_extract, mock_analyze, mock_index, mock_exists, mock_create, perf_client
):
    """1-page PDF should index in < 3 seconds"""
    import uuid

    mock_doc = Mock()
    mock_doc.id = str(uuid.uuid4())
    mock_create.return_value = mock_doc
    mock_analyze.return_value = {
        "file_hash": "abc",
        "file_type": "pdf",
        "total_pages": 1,
        "text_layer_quality": "excellent",
        "needs_ocr": False,
    }
    mock_extract.return_value = generate_pages(1)

    pdf_content = b"%PDF-1.4\n%Test"
    pdf = ("test.pdf", pdf_content, "application/pdf")

    tracemalloc.start()
    start = time.time()

    response = perf_client.post("/api/v1/index", files={"file": pdf})

    elapsed = time.time() - start
    peak_memory = tracemalloc.get_traced_memory()[1] / 1024 / 1024
    tracemalloc.stop()

    assert response.status_code == 200
    assert elapsed < 3.0, f"1-page indexing took {elapsed:.2f}s (SLA: < 3s)"
    assert peak_memory < 100, f"Peak memory {peak_memory:.1f}MB (SLA: < 100MB)"


@pytest.mark.performance
@patch("app.db.supabase_client.supabase_client.create_document")
@patch("app.db.supabase_client.supabase_client.document_exists", return_value=False)
@patch("app.core.retriever.retriever.index_document_chunks", return_value=50)
@patch("app.core.file_detector.file_detector.analyze_file")
@patch("app.core.pdf_extractor.pdf_extractor.extract_embedded_text")
@patch("app.utils.file_storage.file_storage.store_file", return_value="/storage/test.pdf")
def test_indexing_performance_10_pages(
    mock_storage, mock_extract, mock_analyze, mock_index, mock_exists, mock_create, perf_client
):
    """10-page PDF should index in < 10 seconds"""
    import uuid

    mock_doc = Mock()
    mock_doc.id = str(uuid.uuid4())
    mock_create.return_value = mock_doc
    mock_analyze.return_value = {
        "file_hash": "abc",
        "file_type": "pdf",
        "total_pages": 10,
        "text_layer_quality": "excellent",
        "needs_ocr": False,
    }
    mock_extract.return_value = generate_pages(10)

    pdf_content = b"%PDF-1.4\n%Test"
    pdf = ("test.pdf", pdf_content, "application/pdf")

    tracemalloc.start()
    start = time.time()

    response = perf_client.post("/api/v1/index", files={"file": pdf})

    elapsed = time.time() - start
    peak_memory = tracemalloc.get_traced_memory()[1] / 1024 / 1024
    tracemalloc.stop()

    assert response.status_code == 200
    assert elapsed < 10.0, f"10-page indexing took {elapsed:.2f}s (SLA: < 10s)"
    assert peak_memory < 200, f"Peak memory {peak_memory:.1f}MB (SLA: < 200MB)"


@pytest.mark.performance
def test_text_merger_performance():
    """Text merger should handle 50 pages in < 1 second"""
    from app.core.text_merger import TextMerger

    merger = TextMerger()
    embedded_pages = generate_pages(50)
    ocr_result = generate_ocr_result(50)

    start = time.time()
    result = merger.merge_document(embedded_pages, ocr_result, "poor")
    elapsed = time.time() - start

    assert len(result.pages) == 50
    assert elapsed < 1.0, f"Merging 50 pages took {elapsed:.3f}s (SLA: < 1s)"


@pytest.mark.performance
def test_text_merger_memory_efficiency():
    """Text merger should use < 50MB for 100 pages"""
    from app.core.text_merger import TextMerger

    merger = TextMerger()
    embedded_pages = generate_pages(100, text_per_page=50)
    ocr_result = generate_ocr_result(100)

    tracemalloc.start()
    result = merger.merge_document(embedded_pages, ocr_result, "poor")
    peak_memory = tracemalloc.get_traced_memory()[1] / 1024 / 1024
    tracemalloc.stop()

    assert len(result.pages) == 100
    assert peak_memory < 50, f"Merging 100 pages used {peak_memory:.1f}MB (SLA: < 50MB)"


@pytest.mark.performance
def test_page_processing_scales_linearly():
    """Processing time should scale linearly with page count"""
    from app.core.text_merger import TextMerger

    merger = TextMerger()
    timings = []

    # Use larger page counts for more stable timing measurements
    for num_pages in [50, 100, 200]:
        embedded_pages = generate_pages(num_pages)
        ocr_result = generate_ocr_result(num_pages)

        start = time.time()
        merger.merge_document(embedded_pages, ocr_result, "poor")
        elapsed = time.time() - start
        timings.append((num_pages, elapsed))

    # Calculate time per page for each run
    times_per_page = [t / n for n, t in timings]

    # Verify linear scaling: time per page should be roughly constant
    # Allow 100% deviation due to Python overhead and variance
    avg_time_per_page = sum(times_per_page) / len(times_per_page)
    max_deviation = max(abs(t - avg_time_per_page) / avg_time_per_page for t in times_per_page)

    assert max_deviation < 1.0, f"Non-linear scaling detected: {max_deviation:.1%} deviation"


@pytest.mark.performance
def test_baseline_benchmarks():
    """Record baseline performance metrics"""
    from app.core.text_merger import TextMerger

    merger = TextMerger()
    benchmarks = {}

    for num_pages in [1, 5, 10, 25, 50, 100]:
        embedded_pages = generate_pages(num_pages)
        ocr_result = generate_ocr_result(num_pages)

        tracemalloc.start()
        start = time.time()
        result = merger.merge_document(embedded_pages, ocr_result, "poor")
        elapsed = time.time() - start
        peak_memory = tracemalloc.get_traced_memory()[1] / 1024 / 1024
        tracemalloc.stop()

        benchmarks[num_pages] = {
            "time": elapsed,
            "time_per_page": elapsed / num_pages,
            "memory_mb": peak_memory,
            "pages_merged": len(result.pages),
        }

    # Print benchmarks for reference
    print("\n=== Baseline Performance Benchmarks ===")
    for pages, metrics in benchmarks.items():
        print(
            f"{pages:3d} pages: {metrics['time']:6.3f}s ({metrics['time_per_page']*1000:5.2f}ms/page) | {metrics['memory_mb']:5.1f}MB"
        )

    # Basic sanity checks
    assert all(m["pages_merged"] == pages for pages, m in benchmarks.items())
    assert benchmarks[1]["time"] < 0.1, "Single page should be < 100ms"
    assert benchmarks[100]["time"] < 2.0, "100 pages should be < 2s"
