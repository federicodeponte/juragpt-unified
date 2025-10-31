"""Tests for Modal OCR client"""

import pytest
from unittest.mock import Mock, patch
import asyncio

from app.services.modal_client import (
    ModalOCRClient,
    ModalOCRError,
    OCRPageResult,
    OCRDocumentResult,
)


@pytest.fixture
def mock_modal_stub():
    stub = Mock()
    stub.ocr_batch = Mock()
    stub.ocr_batch.remote = Mock(
        return_value=[
            {
                "page_num": 1,
                "full_text": "Page 1",
                "avg_confidence": 0.95,
                "typed_text_pct": 100.0,
                "handwritten_text_pct": 0.0,
                "processing_time_ms": 1500,
                "regions": [{"text": "Test"}],
            },
            {
                "page_num": 2,
                "full_text": "Page 2",
                "avg_confidence": 0.92,
                "typed_text_pct": 80.0,
                "handwritten_text_pct": 20.0,
                "processing_time_ms": 2000,
                "regions": [],
            },
        ]
    )
    stub.ocr_single_page = Mock()
    stub.ocr_single_page.remote = Mock(
        return_value={
            "page_num": 1,
            "full_text": "Single",
            "avg_confidence": 0.94,
            "typed_text_pct": 100.0,
            "handwritten_text_pct": 0.0,
            "processing_time_ms": 1200,
            "regions": [],
        }
    )
    return stub


@pytest.fixture
def mock_pdf_images():
    with patch("app.core.pdf_extractor.pdf_extractor") as m:
        img1, img2 = Mock(), Mock()
        img1.image_base64, img2.image_base64 = "base64_1", "base64_2"
        m.render_all_pages.return_value = [img1, img2]
        yield m


def test_client_initialization():
    client = ModalOCRClient(app_name="test", timeout=120, enabled=False)
    assert client.app_name == "test" and client.timeout == 120


def test_client_unavailable():
    with patch("app.services.modal_client.MODAL_AVAILABLE", False):
        assert not ModalOCRClient().is_available()


@pytest.mark.asyncio
async def test_ocr_disabled():
    with patch("app.services.modal_client.MODAL_AVAILABLE", False):
        with pytest.raises(ModalOCRError, match="not available"):
            await ModalOCRClient(enabled=False).process_document_ocr(
                b"test", enable_handwriting=True
            )


@pytest.mark.asyncio
async def test_ocr_no_pages():
    with patch("app.core.pdf_extractor.pdf_extractor") as m:
        m.render_all_pages.return_value = []
        client = ModalOCRClient(enabled=True)
        client.available = client.enabled = True
        with pytest.raises(ModalOCRError, match="Failed to render"):
            await client.process_document_ocr(b"test", enable_handwriting=True)


@pytest.mark.asyncio
async def test_ocr_partial_failure(mock_modal_stub, mock_pdf_images):
    mock_modal_stub.ocr_batch.remote.return_value = [
        {
            "page_num": 1,
            "full_text": "OK",
            "avg_confidence": 0.95,
            "typed_text_pct": 100.0,
            "handwritten_text_pct": 0.0,
            "processing_time_ms": 1500,
            "regions": [],
        },
        {
            "page_num": 2,
            "full_text": "",
            "avg_confidence": 0.0,
            "typed_text_pct": 0.0,
            "handwritten_text_pct": 0.0,
            "processing_time_ms": 100,
            "regions": [],
            "error": "Failed",
        },
    ]
    client = ModalOCRClient(enabled=True)
    client.stub, client.available, client.enabled = mock_modal_stub, True, True
    result = await client.process_document_ocr(b"test", enable_handwriting=True)
    assert result.pages_processed == 1 and result.pages_failed == 1


@pytest.mark.asyncio
async def test_ocr_timeout(mock_modal_stub, mock_pdf_images):
    with patch("asyncio.to_thread", side_effect=asyncio.TimeoutError()):
        client = ModalOCRClient(enabled=True, timeout=1)
        client.stub, client.available, client.enabled = mock_modal_stub, True, True
        with pytest.raises(ModalOCRError, match="Timeout"):
            await client.process_document_ocr(b"test", enable_handwriting=True)


@pytest.mark.asyncio
async def test_single_page_ocr(mock_modal_stub):
    client = ModalOCRClient(enabled=True)
    client.stub, client.available, client.enabled = mock_modal_stub, True, True
    result = await client.process_page_ocr("base64", 1, True)
    assert isinstance(result, OCRPageResult) and result.page_num == 1


def test_parse_result_valid():
    result = ModalOCRClient(enabled=False)._parse_page_result(
        {
            "page_num": 1,
            "full_text": "Test",
            "avg_confidence": 0.95,
            "typed_text_pct": 80.0,
            "handwritten_text_pct": 20.0,
            "processing_time_ms": 1500,
            "regions": [{"text": "T"}],
        }
    )
    assert result.page_num == 1 and result.avg_confidence == 0.95


def test_parse_result_missing_fields():
    with pytest.raises(ValueError, match="Missing required"):
        ModalOCRClient(enabled=False)._parse_page_result({"page_num": 1})


def test_availability():
    client = ModalOCRClient(enabled=True)
    client.available = client.enabled = True
    assert client.is_available()

    assert not ModalOCRClient(enabled=False).is_available()
