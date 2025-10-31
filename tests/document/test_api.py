"""Integration tests for API endpoints"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, Mock, AsyncMock, MagicMock
import uuid

# Mock SentenceTransformer before app imports to prevent model download
with patch("sentence_transformers.SentenceTransformer") as mock_st:
    mock_model = MagicMock()
    mock_model.encode.return_value = [0.1] * 384
    mock_model.get_sentence_embedding_dimension.return_value = 384
    mock_st.return_value = mock_model

    from app.main import app


class TestAPIEndpoints:
    """Test FastAPI endpoints"""

    @pytest.fixture
    def client(self):
        from app.auth.models import User
        from app.auth.middleware import require_auth
        from app.auth.rate_limit import rate_limiter
        from app.auth.usage import usage_tracker
        from datetime import datetime

        # Mock user for auth
        mock_user = User(id=uuid.uuid4(), email="test@example.com", created_at=datetime.utcnow())

        # Override auth dependency
        app.dependency_overrides[require_auth] = lambda: mock_user

        # Mock rate limiter and usage tracker
        with patch.object(rate_limiter, "enforce_rate_limit", new_callable=AsyncMock), patch.object(
            usage_tracker, "enforce_quota", new_callable=AsyncMock
        ), patch.object(usage_tracker, "increment_usage", new_callable=AsyncMock):
            yield TestClient(app)

        # Clean up
        app.dependency_overrides.clear()

    def test_root_endpoint(self, client):
        """Test root endpoint"""
        response = client.get("/")

        assert response.status_code == 200
        data = response.json()
        assert "service" in data
        assert "JuraGPT" in data["service"]

    def test_health_check(self, client):
        """Test health check endpoint"""
        with patch("app.utils.redis_client.redis_client.health_check", return_value=True):
            response = client.get("/api/v1/health")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert data["redis"] is True

    def test_health_check_degraded(self, client):
        """Test health check when Redis is down"""
        with patch("app.utils.redis_client.redis_client.health_check", return_value=False):
            response = client.get("/api/v1/health")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "degraded"
            assert data["redis"] is False

    def test_index_endpoint(self, client):
        """Test document indexing endpoint"""
        from app.core.retriever import get_retriever
        from app.core.document_parser import DocumentParser

        # Mock DocumentParser to return test sections
        mock_sections = [
            {"section_id": "§1", "content": "Test section 1", "chunk_type": "section", "position": 0},
            {"section_id": "§2", "content": "Test section 2", "chunk_type": "section", "position": 1},
        ]

        with patch("app.db.supabase_client.supabase_client.create_document") as mock_create, \
             patch("app.db.supabase_client.supabase_client.document_exists", return_value=False), \
             patch.object(get_retriever(), "index_document_chunks", return_value=42), \
             patch.object(DocumentParser, "parse_document", return_value=mock_sections):

            # Mock database responses
            mock_doc = Mock()
            mock_doc.id = uuid.uuid4()
            mock_create.return_value = mock_doc

            # Create test file
            files = {"file": ("test.txt", b"Test document content", "text/plain")}

            response = client.post("/api/v1/index", files=files)

            assert response.status_code == 200
            data = response.json()
            assert "document_id" in data
            assert data["chunks_created"] == 42
            assert data["status"] == "indexed"

    def test_index_duplicate_document(self, client):
        """Test indexing duplicate document"""
        with patch("app.db.supabase_client.supabase_client.document_exists", return_value=True):
            files = {"file": ("test.txt", b"Test content", "text/plain")}

            response = client.post("/api/v1/index", files=files)

            assert response.status_code == 409  # Conflict
            assert "already indexed" in response.json()["detail"]

    @patch("app.db.supabase_client.supabase_client.get_document")
    @patch("app.core.retriever.retriever.retrieve")
    @patch("app.core.pii_anonymizer.pii_anonymizer.anonymize")
    @patch("app.core.pii_anonymizer.pii_anonymizer.deanonymize")
    @patch("app.core.pii_anonymizer.pii_anonymizer.verify_no_pii_leakage", return_value=True)
    @patch("app.core.gemini_client.gemini_client.analyze")
    @patch("app.core.gemini_client.gemini_client.verify_answer")
    @patch("app.core.verifier.verifier.verify_answer")
    @patch("app.core.verifier.verifier.extract_citations")
    @patch("app.db.supabase_client.supabase_client.log_query")
    @patch("app.utils.redis_client.redis_client.delete_pii_mapping")
    def test_analyze_endpoint_full_pipeline(
        self,
        mock_redis_delete,
        mock_log,
        mock_extract_citations,
        mock_verify,
        mock_gemini_verify,
        mock_gemini_analyze,
        mock_pii_verify,
        mock_deanon,
        mock_anon,
        mock_retrieve,
        mock_get_doc,
        client,
    ):
        """Test full analyze pipeline"""
        # Setup mocks
        doc_id = str(uuid.uuid4())

        mock_doc = Mock()
        mock_doc.id = uuid.UUID(doc_id)
        mock_get_doc.return_value = mock_doc

        mock_retrieve.return_value = [
            Mock(
                chunk_id=uuid.uuid4(),
                section_id="§5.2",
                content="Test content",
                similarity=0.95,
                parent_content=None,
                sibling_contents=[],
            )
        ]

        mock_anon.return_value = ("anonymized query", {})
        mock_deanon.return_value = "According to §5.2: Answer"

        mock_gemini_analyze.return_value = {
            "answer": "According to <SECTION_1>: Answer",
            "latency_ms": 1500,
            "tokens_used": 150,
            "model_version": "gemini-2.5-pro",
        }

        mock_gemini_verify.return_value = {
            "is_supported": True,
            "verification_details": "✓ All supported",
        }

        mock_verify_result = Mock()
        mock_verify_result.confidence = 0.87
        mock_verify_result.unsupported_statements = []
        mock_verify.return_value = mock_verify_result

        mock_extract_citations.return_value = [
            Mock(section_id="§5.2", content="Test content", confidence=0.94, chunk_id=uuid.uuid4())
        ]

        # Make request
        request_data = {"file_id": doc_id, "query": "Was regelt §5?", "top_k": 5}

        response = client.post("/api/v1/analyze", json=request_data)

        assert response.status_code == 200
        data = response.json()

        assert "answer" in data
        assert "citations" in data
        assert "confidence" in data
        assert "request_id" in data
        assert len(data["citations"]) > 0

    def test_analyze_document_not_found(self, client):
        """Test analyze with non-existent document"""
        with patch("app.db.supabase_client.supabase_client.get_document", return_value=None):
            request_data = {"file_id": str(uuid.uuid4()), "query": "Test query"}

            response = client.post("/api/v1/analyze", json=request_data)

            assert response.status_code == 404
            assert "not found" in response.json()["detail"]

    def test_analyze_invalid_uuid(self, client):
        """Test analyze with invalid UUID"""
        request_data = {"file_id": "invalid-uuid", "query": "Test query"}

        response = client.post("/api/v1/analyze", json=request_data)

        assert response.status_code == 422  # Validation error

    @patch("app.db.supabase_client.supabase_client.get_query_logs")
    def test_history_endpoint(self, mock_get_logs, client):
        """Test query history endpoint"""
        from app.db.models import QueryLogDB
        from datetime import datetime

        doc_id = str(uuid.uuid4())

        mock_logs = [
            QueryLogDB(
                id=uuid.uuid4(),
                document_id=uuid.UUID(doc_id),
                query_hash="abc123",
                response_hash="def456",
                created_at=datetime.utcnow(),
                latency_ms=2000,
                tokens_used=150,
                model_version="gemini-2.5-pro",
                citations_count=3,
                confidence_score=0.85,
                error_message=None,
            )
        ]
        mock_get_logs.return_value = mock_logs

        response = client.get(f"/api/v1/history/{doc_id}")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_cors_headers(self, client):
        """Test CORS headers are present"""
        response = client.get("/api/v1/health")

        # Should have CORS headers on GET request
        assert response.status_code == 200
        # CORS middleware adds headers automatically
        assert "access-control-allow-origin" in response.headers

    def test_security_headers(self, client):
        """Test OWASP security headers are present"""
        response = client.get("/api/v1/health")

        assert response.status_code == 200

        # Check all OWASP recommended headers
        assert response.headers.get("x-content-type-options") == "nosniff"
        assert response.headers.get("x-frame-options") == "DENY"
        assert response.headers.get("x-xss-protection") == "1; mode=block"
        assert "default-src 'none'" in response.headers.get("content-security-policy", "")
        assert response.headers.get("referrer-policy") == "strict-origin-when-cross-origin"
        assert "geolocation=()" in response.headers.get("permissions-policy", "")
        assert response.headers.get("x-permitted-cross-domain-policies") == "none"

        # HSTS should NOT be present in test environment (only production)
        assert "strict-transport-security" not in response.headers

    def test_security_headers_cache_control(self, client):
        """Test Cache-Control header on sensitive endpoints"""
        # Health endpoint should allow caching
        health_response = client.get("/api/v1/health")
        assert "no-store" not in health_response.headers.get("cache-control", "")

        # Analyze endpoint should prevent caching (but we need to mock it)
        from app.db.supabase_client import supabase_client

        with patch.object(supabase_client, "get_document", return_value=None):
            analyze_response = client.post(
                "/api/v1/analyze", json={"file_id": str(uuid.uuid4()), "query": "test"}
            )
            # Should have Cache-Control even on error responses
            assert "cache-control" in analyze_response.headers
