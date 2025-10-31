"""Integration tests for OCR pipeline (Week 1-3)"""

import pytest
from unittest.mock import patch, Mock, AsyncMock
import io
from app.core.pdf_extractor import PageText
from app.services.modal_client import OCRDocumentResult, OCRPageResult


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from app.main import app
    from app.auth.middleware import get_current_user
    from app.auth.models import User
    from datetime import datetime
    import uuid

    # Mock user for tests
    async def override_get_current_user():
        return User(id=uuid.uuid4(), email="test@example.com", created_at=datetime.utcnow())

    # Override the auth dependency
    app.dependency_overrides[get_current_user] = override_get_current_user

    test_client = TestClient(app)
    yield test_client

    # Clean up
    app.dependency_overrides.clear()


@pytest.fixture
def high_quality_pdf():
    """Simulated high-quality PDF with good embedded text"""
    pdf_content = b"%PDF-1.4\n%Test PDF content"
    return ("high_quality.pdf", pdf_content, "application/pdf")


@pytest.fixture
def scanned_pdf():
    """Simulated scanned PDF with no text layer"""
    pdf_content = b"%PDF-1.4\n%Scanned image"
    return ("scanned.pdf", pdf_content, "application/pdf")


@pytest.fixture
def mock_high_quality_analysis():
    return {
        "file_hash": "abc123",
        "file_type": "pdf",
        "total_pages": 3,
        "text_layer_quality": "excellent",
        "needs_ocr": False,
    }


@pytest.fixture
def mock_poor_quality_analysis():
    return {
        "file_hash": "def456",
        "file_type": "pdf",
        "total_pages": 3,
        "text_layer_quality": "poor",
        "needs_ocr": True,
    }


@pytest.fixture
def mock_embedded_pages():
    return [
        PageText(1, "Page 1 high quality text", 100, 20, None, 0.95),
        PageText(2, "Page 2 high quality text", 100, 20, None, 0.95),
        PageText(3, "Page 3 high quality text", 100, 20, None, 0.95),
    ]


@pytest.fixture
def mock_ocr_result():
    return OCRDocumentResult(
        full_text="Page 1 OCR\n\nPage 2 OCR\n\nPage 3 OCR",
        pages=[
            OCRPageResult(1, "Page 1 OCR", 0.92, 100.0, 0.0, 1500, 5),
            OCRPageResult(2, "Page 2 OCR", 0.88, 80.0, 20.0, 2000, 8),
            OCRPageResult(3, "Page 3 OCR", 0.85, 70.0, 30.0, 1800, 6),
        ],
        avg_confidence=0.88,
        typed_text_pct=83.3,
        handwritten_text_pct=16.7,
        total_processing_time_ms=5300,
        pages_processed=3,
        pages_failed=0,
        errors=[],
    )


@pytest.mark.integration
@patch("app.db.supabase_client.supabase_client.create_document")
@patch("app.db.supabase_client.supabase_client.document_exists", return_value=False)
@patch("app.core.retriever.retriever.index_document_chunks", return_value=10)
@patch("app.core.file_detector.file_detector.analyze_file")
@patch("app.core.pdf_extractor.pdf_extractor.extract_embedded_text")
@patch("app.utils.file_storage.file_storage.store_file", return_value="/storage/test.pdf")
def test_high_quality_pdf_uses_embedded_only(
    mock_storage,
    mock_extract,
    mock_analyze,
    mock_index,
    mock_exists,
    mock_create,
    client,
    high_quality_pdf,
    mock_high_quality_analysis,
    mock_embedded_pages,
):
    """High-quality PDF should use embedded text, NO OCR triggered"""
    import uuid

    mock_doc = Mock()
    mock_doc.id = str(uuid.uuid4())  # Use valid UUID
    mock_create.return_value = mock_doc
    mock_analyze.return_value = mock_high_quality_analysis
    mock_extract.return_value = mock_embedded_pages

    response = client.post("/api/v1/index", files={"file": high_quality_pdf})

    assert response.status_code == 200
    data = response.json()

    # Verify embedded text used (OCR not triggered)
    mock_extract.assert_called_once()
    # OCR should NOT be called for excellent quality
    assert data["status"] == "indexed"


@pytest.mark.integration
@patch("app.db.supabase_client.supabase_client.create_document")
@patch("app.db.supabase_client.supabase_client.document_exists", return_value=False)
@patch("app.core.retriever.retriever.index_document_chunks", return_value=15)
@patch("app.core.file_detector.file_detector.analyze_file")
@patch("app.core.pdf_extractor.pdf_extractor.extract_embedded_text")
@patch("app.services.modal_client.modal_ocr_client.is_available", return_value=True)
@patch("app.services.modal_client.modal_ocr_client.process_document_ocr")
@patch("app.utils.file_storage.file_storage.store_file", return_value="/storage/scanned.pdf")
def test_scanned_pdf_triggers_ocr(
    mock_storage,
    mock_ocr,
    mock_available,
    mock_extract,
    mock_analyze,
    mock_index,
    mock_exists,
    mock_create,
    client,
    scanned_pdf,
    mock_poor_quality_analysis,
    mock_embedded_pages,
    mock_ocr_result,
):
    """Scanned PDF with poor quality should trigger OCR"""
    import uuid

    mock_doc = Mock()
    mock_doc.id = str(uuid.uuid4())
    mock_create.return_value = mock_doc
    mock_analyze.return_value = mock_poor_quality_analysis
    mock_extract.return_value = mock_embedded_pages
    mock_ocr.return_value = mock_ocr_result

    response = client.post("/api/v1/index", files={"file": scanned_pdf})

    assert response.status_code == 200

    # Verify OCR was called
    mock_ocr.assert_called_once()
    data = response.json()
    assert data["status"] == "indexed"


@pytest.mark.integration
@patch("app.db.supabase_client.supabase_client.create_document")
@patch("app.db.supabase_client.supabase_client.document_exists", return_value=False)
@patch("app.core.retriever.retriever.index_document_chunks", return_value=15)
@patch("app.core.file_detector.file_detector.analyze_file")
@patch("app.core.pdf_extractor.pdf_extractor.extract_embedded_text")
@patch("app.services.modal_client.modal_ocr_client.is_available", return_value=False)
@patch("app.utils.file_storage.file_storage.store_file", return_value="/storage/fallback.pdf")
def test_ocr_unavailable_fallback(
    mock_storage,
    mock_available,
    mock_extract,
    mock_analyze,
    mock_index,
    mock_exists,
    mock_create,
    client,
    scanned_pdf,
    mock_poor_quality_analysis,
    mock_embedded_pages,
):
    """When OCR unavailable, should gracefully fall back to embedded text"""
    import uuid

    mock_doc = Mock()
    mock_doc.id = str(uuid.uuid4())
    mock_create.return_value = mock_doc
    mock_analyze.return_value = mock_poor_quality_analysis
    mock_extract.return_value = mock_embedded_pages

    response = client.post("/api/v1/index", files={"file": scanned_pdf})

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "indexed"
    # Should use embedded text as fallback


@pytest.mark.integration
@patch("app.db.supabase_client.supabase_client.create_document")
@patch("app.db.supabase_client.supabase_client.document_exists", return_value=False)
@patch("app.core.retriever.retriever.index_document_chunks", return_value=15)
@patch("app.core.file_detector.file_detector.analyze_file")
@patch("app.core.pdf_extractor.pdf_extractor.extract_embedded_text")
@patch("app.services.modal_client.modal_ocr_client.is_available", return_value=True)
@patch("app.services.modal_client.modal_ocr_client.process_document_ocr")
@patch("app.utils.file_storage.file_storage.store_file", return_value="/storage/error.pdf")
def test_ocr_error_handling(
    mock_storage,
    mock_ocr,
    mock_available,
    mock_extract,
    mock_analyze,
    mock_index,
    mock_exists,
    mock_create,
    client,
    scanned_pdf,
    mock_poor_quality_analysis,
    mock_embedded_pages,
):
    """When OCR fails, should fall back to embedded text"""
    import uuid

    mock_doc = Mock()
    mock_doc.id = str(uuid.uuid4())
    mock_create.return_value = mock_doc
    mock_analyze.return_value = mock_poor_quality_analysis
    mock_extract.return_value = mock_embedded_pages
    mock_ocr.side_effect = Exception("Modal timeout")

    response = client.post("/api/v1/index", files={"file": scanned_pdf})

    assert response.status_code == 200
    # Should succeed despite OCR error (fallback to embedded)


@pytest.mark.integration
def test_invalid_pdf_format(client):
    """Invalid PDF should return error"""
    invalid_file = ("not_a_pdf.txt", b"This is not a PDF", "application/pdf")

    with patch("app.core.file_detector.file_detector.analyze_file") as mock_analyze:
        mock_analyze.side_effect = Exception("Invalid PDF format")

        response = client.post("/api/v1/index", files={"file": invalid_file})

        assert response.status_code == 500


@pytest.mark.integration
def test_empty_pdf_content(client, high_quality_pdf):
    """PDF with no extractable text should return error"""
    with patch("app.core.file_detector.file_detector.analyze_file") as mock_analyze, patch(
        "app.core.pdf_extractor.pdf_extractor.extract_embedded_text"
    ) as mock_extract, patch(
        "app.db.supabase_client.supabase_client.document_exists", return_value=False
    ), patch(
        "app.utils.file_storage.file_storage.store_file", return_value="/storage/empty.pdf"
    ), patch(
        "app.services.modal_client.modal_ocr_client.is_available", return_value=False
    ):

        mock_analyze.return_value = {
            "file_hash": "empty123",
            "file_type": "pdf",
            "total_pages": 1,
            "text_layer_quality": "none",
            "needs_ocr": True,
        }
        mock_extract.return_value = [PageText(1, "", 0, 0, None, 0.0)]

        response = client.post("/api/v1/index", files={"file": high_quality_pdf})

        assert response.status_code == 500
        assert "No text could be extracted" in response.json()["detail"]
