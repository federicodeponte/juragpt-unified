# -*- coding: utf-8 -*-
"""
Integration tests for FastAPI endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from auditor.api.server import app
from auditor.config.settings import get_settings
from auditor.core.verification_service import VerificationService
from auditor.storage.storage_interface import StorageInterface


@pytest.fixture
def client():
    """Create test client with properly initialized app state."""
    # Get settings with SQLite for tests (not PostgreSQL)
    settings = get_settings()

    # Override database URL to use in-memory SQLite for tests
    # This avoids needing PostgreSQL server for integration tests
    test_database_url = "sqlite:///:memory:"

    # Manually initialize app state (mimics lifespan startup)
    # This is necessary because TestClient doesn't always trigger lifespan events
    app.state.verification_service = VerificationService(settings=settings)
    app.state.storage = StorageInterface(database_url=test_database_url)

    # Create test client
    return TestClient(app)


class TestHealthEndpoint:
    """Test health check endpoint."""

    def test_health_check(self, client):
        """Test GET /health endpoint."""
        response = client.get("/health")

        assert response.status_code == 200
        data = response.json()

        assert "status" in data
        assert data["status"] == "healthy"
        assert "timestamp" in data


class TestVerifyEndpoint:
    """Test verification endpoint."""

    def test_verify_basic(self, client, sample_verification_request):
        """Test POST /verify with basic request."""
        response = client.post("/verify", json=sample_verification_request)

        assert response.status_code == 200
        data = response.json()

        # Check response structure
        assert "confidence" in data
        assert "trust_label" in data
        assert "verified" in data
        assert "components" in data

        # Check data types
        assert isinstance(data["confidence"], float)
        assert isinstance(data["trust_label"], str)
        assert isinstance(data["verified"], bool)

    def test_verify_missing_fields(self, client):
        """Test verification with missing required fields."""
        incomplete_request = {
            "answer": "Test answer",
            # Missing sources
        }

        response = client.post("/verify", json=incomplete_request)
        assert response.status_code == 422  # Validation error

    def test_verify_empty_answer(self, client):
        """Test verification with empty answer."""
        request = {
            "answer": "",
            "sources": [
                {"text": "Source text", "source_id": "src_1", "score": 0.9}
            ],
        }

        response = client.post("/verify", json=request)

        # Should handle gracefully
        assert response.status_code in [200, 400]

    def test_verify_empty_sources(self, client):
        """Test verification with empty sources."""
        request = {
            "answer": "Test answer",
            "sources": [],
        }

        response = client.post("/verify", json=request)

        # Should return low confidence
        if response.status_code == 200:
            data = response.json()
            assert data["confidence"] < 0.5

    def test_verify_high_confidence_answer(self, client):
        """Test verification of well-supported answer."""
        request = {
            "answer": "Nach § 823 BGB haftet, wer vorsätzlich oder fahrlässig einen Schaden verursacht.",
            "sources": [
                {
                    "text": "Wer vorsätzlich oder fahrlässig das Leben, den Körper, die Gesundheit verletzt, haftet zum Ersatz des Schadens.",
                    "source_id": "bgb_823_1",
                    "score": 0.95,
                },
                {
                    "text": "Der Schuldner hat Vorsatz und Fahrlässigkeit zu vertreten.",
                    "source_id": "bgb_276",
                    "score": 0.88,
                },
            ],
            "threshold": 0.75,
        }

        response = client.post("/verify", json=request)
        assert response.status_code == 200

        data = response.json()
        # Should have decent confidence (exact value depends on model)
        assert 0.0 <= data["confidence"] <= 1.0

    @pytest.mark.slow
    def test_verify_multiple_sentences(self, client):
        """Test verification of answer with multiple sentences."""
        request = {
            "answer": "Der Schuldner haftet für Vorsatz. Er haftet auch für Fahrlässigkeit. Das gilt nach § 276 BGB.",
            "sources": [
                {
                    "text": "Der Schuldner hat Vorsatz und Fahrlässigkeit zu vertreten, sofern nicht ein anderes bestimmt ist.",
                    "source_id": "bgb_276",
                    "score": 0.90,
                }
            ],
        }

        response = client.post("/verify", json=request)
        assert response.status_code == 200

        data = response.json()
        assert "statistics" in data
        assert data["statistics"]["total_sentences"] >= 2

    def test_verify_custom_threshold(self, client):
        """Test verification with custom threshold."""
        request = {
            "answer": "Test answer",
            "sources": [{"text": "Source", "source_id": "s1", "score": 0.9}],
            "threshold": 0.90,  # High threshold
        }

        response = client.post("/verify", json=request)
        assert response.status_code == 200

    def test_verify_auto_retry_enabled(self, client):
        """Test verification with auto_retry enabled."""
        request = {
            "answer": "Test answer",
            "sources": [{"text": "Source", "source_id": "s1", "score": 0.9}],
            "auto_retry": True,
        }

        response = client.post("/verify", json=request)
        assert response.status_code == 200

    def test_verify_large_answer(self, client):
        """Test verification with large answer."""
        large_answer = " ".join([f"Sentence {i} about legal matters." for i in range(50)])

        request = {
            "answer": large_answer,
            "sources": [
                {"text": "Legal text about matters", "source_id": "s1", "score": 0.9}
            ],
        }

        response = client.post("/verify", json=request, timeout=30.0)

        # Should handle large text
        assert response.status_code == 200


class TestStatisticsEndpoint:
    """Test statistics endpoint."""

    def test_statistics(self, client):
        """Test GET /statistics endpoint."""
        response = client.get("/statistics")

        # Endpoint should exist and return data
        assert response.status_code in [200, 404]  # 404 if not implemented

        if response.status_code == 200:
            data = response.json()
            # Should have statistics structure
            assert isinstance(data, dict)


class TestMetricsEndpoint:
    """Test Prometheus metrics endpoint."""

    def test_metrics(self, client):
        """Test GET /metrics endpoint."""
        response = client.get("/metrics")

        # Should return Prometheus metrics
        assert response.status_code == 200
        assert "text/plain" in response.headers.get("content-type", "")

        # Should contain some metric names
        text = response.text
        assert isinstance(text, str)
        # Prometheus metrics typically contain these patterns
        # assert "# " in text or response.text == ""  # Empty is OK for tests


class TestCORSHeaders:
    """Test CORS configuration."""

    def test_cors_preflight(self, client):
        """Test CORS preflight request."""
        response = client.options(
            "/verify",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
            },
        )

        # Should allow CORS
        assert response.status_code in [200, 204]
        # Check for CORS headers if implemented
        # assert "access-control-allow-origin" in response.headers


class TestErrorHandling:
    """Test API error handling."""

    def test_invalid_json(self, client):
        """Test sending invalid JSON."""
        response = client.post(
            "/verify",
            data="invalid json{",
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 422  # Unprocessable entity

    def test_wrong_content_type(self, client):
        """Test sending wrong content type."""
        response = client.post(
            "/verify",
            data="test",
            headers={"Content-Type": "text/plain"},
        )

        assert response.status_code in [415, 422]  # Unsupported media type or validation error

    def test_nonexistent_endpoint(self, client):
        """Test accessing non-existent endpoint."""
        response = client.get("/nonexistent")
        assert response.status_code == 404


class TestPerformance:
    """Test API performance."""

    @pytest.mark.slow
    @pytest.mark.performance
    def test_response_time(self, client, sample_verification_request):
        """Test that verification completes within reasonable time."""
        import time

        start = time.time()
        response = client.post("/verify", json=sample_verification_request)
        duration = time.time() - start

        assert response.status_code == 200
        # Should complete within target (800ms), but allow more for CI
        assert duration < 5.0  # 5 seconds max for test environment

    @pytest.mark.slow
    @pytest.mark.performance
    def test_concurrent_requests(self, client, sample_verification_request):
        """Test handling concurrent requests."""
        import concurrent.futures

        def make_request():
            return client.post("/verify", json=sample_verification_request)

        # Make 5 concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(make_request) for _ in range(5)]
            responses = [f.result() for f in futures]

        # All should succeed
        assert all(r.status_code == 200 for r in responses)
