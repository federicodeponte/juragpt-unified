"""
Pytest configuration and fixtures for JuraGPT tests
"""

import pytest
import uuid
import sys
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

# Mock Presidio modules before any app imports
sys.modules["presidio_analyzer"] = MagicMock()
sys.modules["presidio_analyzer.nlp_engine"] = MagicMock()
sys.modules["presidio_anonymizer"] = MagicMock()
sys.modules["presidio_anonymizer.entities"] = MagicMock()


@pytest.fixture(autouse=True)
def mock_settings():
    """Mock application settings for all tests"""
    mock_settings = Mock()
    mock_settings.supabase_url = "https://test.supabase.co"
    mock_settings.supabase_key = "test-key"
    mock_settings.supabase_service_role_key = "test-service-key"
    mock_settings.gemini_api_key = "test-gemini-key"
    mock_settings.gemini_model = "gemini-2.5-pro"
    mock_settings.gemini_temperature = 0.1
    mock_settings.gemini_endpoint = "https://generativelanguage.googleapis.com"
    mock_settings.redis_host = "localhost"
    mock_settings.redis_port = 6379
    mock_settings.redis_password = ""
    mock_settings.redis_db = 0
    # Redis Connection Pool (Phase 15)
    mock_settings.redis_max_connections = 50
    mock_settings.redis_socket_timeout = 5
    mock_settings.redis_socket_connect_timeout = 5
    mock_settings.redis_socket_keepalive = True
    mock_settings.redis_health_check_interval = 30
    # Redis Caching (Phase 15)
    mock_settings.cache_enabled = True
    mock_settings.cache_query_results_ttl = 3600
    mock_settings.cache_documents_ttl = 7200
    mock_settings.cache_query_logs_ttl = 300
    mock_settings.environment = "test"
    mock_settings.log_level = "INFO"
    mock_settings.api_v1_prefix = "/api/v1"
    mock_settings.secret_key = "test-secret"
    mock_settings.allowed_origins = ["http://localhost:3000"]
    # Use a valid test model that doesn't require download
    mock_settings.embedding_model = "sentence-transformers/all-MiniLM-L6-v2"
    mock_settings.pii_mapping_ttl = 300
    mock_settings.pii_confidence_threshold = 0.7
    mock_settings.default_top_k = 5
    mock_settings.max_chunk_size = 1000
    mock_settings.chunk_overlap = 100
    mock_settings.ollama_endpoint = "http://localhost:11434"
    mock_settings.ollama_model = "mistral:7b"
    mock_settings.use_local_verifier = True
    mock_settings.chunks_retention_days = 730
    mock_settings.logs_retention_days = 90
    mock_settings.usage_retention_months = 13
    mock_settings.modal_token_id = "test-modal-id"
    mock_settings.modal_token_secret = "test-modal-secret"
    mock_settings.modal_app_name = "test-ocr"
    mock_settings.modal_timeout = 300
    mock_settings.modal_enabled = False
    mock_settings.enable_handwriting_ocr = True
    mock_settings.sentry_dsn = ""  # Disable Sentry in tests
    mock_settings.sentry_environment = "test"
    mock_settings.sentry_traces_sample_rate = 0.0
    mock_settings.sentry_profiles_sample_rate = 0.0

    # Create mock SentenceTransformer
    import numpy as np
    mock_model = MagicMock()
    mock_model.encode.return_value = np.array([0.1] * 384)  # Mock embedding as numpy array
    mock_model.get_sentence_embedding_dimension.return_value = 384

    with patch("app.config.settings", mock_settings), patch(
        "sentence_transformers.SentenceTransformer", return_value=mock_model
    ), patch("app.core.retriever._retriever_instance", None):
        # Reset retriever instance for each test to ensure clean state
        yield mock_settings


@pytest.fixture
def sample_user():
    """Create a sample user for testing"""
    from app.auth.models import User

    return User(id=uuid.uuid4(), email="test@example.com", created_at=datetime.utcnow())


@pytest.fixture
def sample_user_usage():
    """Create sample user usage for testing"""
    from app.auth.models import UserUsage

    return UserUsage(
        user_id=uuid.uuid4(),
        month="2025-01",
        tokens_used=1000,
        queries_count=10,
        documents_indexed=2,
    )


@pytest.fixture
def mock_pii_components():
    """Mock Presidio and Redis components for PII tests"""
    from unittest.mock import MagicMock, patch

    # Mock AnalyzerResult
    def create_analyzer_result(entity_type, start, end, score=0.85):
        result = MagicMock()
        result.entity_type = entity_type
        result.start = start
        result.end = end
        result.score = score
        return result

    # Mock AnonymizerResult
    def create_anonymizer_result(text):
        result = MagicMock()
        result.text = text
        return result

    # Mock AnalyzerEngine
    mock_analyzer = MagicMock()

    def mock_analyze(text, language="de", score_threshold=0.7):
        """Mock analyzer that detects common PII patterns"""
        results = []

        # Detect person names (simple heuristic: Title + capitalized words)
        if "Dr. Eva Müller" in text:
            results.append(create_analyzer_result("PERSON", text.index("Dr. Eva Müller"), text.index("Dr. Eva Müller") + 13))
        elif "Eva Müller" in text:
            results.append(create_analyzer_result("PERSON", text.index("Eva Müller"), text.index("Eva Müller") + 10))

        if "Müller GmbH" in text:
            results.append(create_analyzer_result("ORG", text.index("Müller GmbH"), text.index("Müller GmbH") + 11))
        if "Schmidt AG" in text:
            results.append(create_analyzer_result("ORG", text.index("Schmidt AG"), text.index("Schmidt AG") + 10))

        # Detect locations
        if "Berlin" in text:
            results.append(create_analyzer_result("LOCATION", text.index("Berlin"), text.index("Berlin") + 6))
        if "München" in text:
            results.append(create_analyzer_result("LOCATION", text.index("München"), text.index("München") + 7))

        # Detect IBAN
        if "DE89370400440532013000" in text:
            results.append(create_analyzer_result("IBAN", text.index("DE89370400440532013000"), text.index("DE89370400440532013000") + 22))

        # Detect case numbers
        if "1 C 234/23" in text:
            results.append(create_analyzer_result("CASE_NUMBER", text.index("1 C 234/23"), text.index("1 C 234/23") + 10))

        return results

    mock_analyzer.analyze = mock_analyze

    # Mock AnonymizerEngine
    mock_anonymizer = MagicMock()

    def mock_anonymize(text, analyzer_results, operators=None):
        """Mock anonymizer that replaces PII with placeholders"""
        anonymized_text = text

        # Sort results by start position in reverse to avoid index shifting
        sorted_results = sorted(analyzer_results, key=lambda r: r.start, reverse=True)

        entity_counters = {}
        for result in sorted_results:
            entity_type = result.entity_type

            # Generate placeholder
            if entity_type not in entity_counters:
                entity_counters[entity_type] = 0
            entity_counters[entity_type] += 1
            placeholder = f"<{entity_type}_{entity_counters[entity_type]}>"

            # Replace in text
            anonymized_text = anonymized_text[:result.start] + placeholder + anonymized_text[result.end:]

        return create_anonymizer_result(anonymized_text)

    mock_anonymizer.anonymize = mock_anonymize

    # Mock Redis client
    redis_storage = {}

    mock_redis = MagicMock()
    mock_redis.store_pii_mapping = lambda request_id, mapping: redis_storage.update({request_id: mapping})
    mock_redis.get_pii_mapping = lambda request_id: redis_storage.get(request_id)
    mock_redis.delete_pii_mapping = lambda request_id: redis_storage.pop(request_id, None)
    mock_redis.mapping_exists = lambda request_id: request_id in redis_storage
    mock_redis.get_ttl = lambda request_id: 300 if request_id in redis_storage else -1

    with patch("app.core.pii_anonymizer.AnalyzerEngine", return_value=mock_analyzer), \
         patch("app.core.pii_anonymizer.AnonymizerEngine", return_value=mock_anonymizer), \
         patch("app.core.pii_anonymizer.redis_client", mock_redis), \
         patch("app.utils.redis_client.redis_client", mock_redis):
        yield {
            "analyzer": mock_analyzer,
            "anonymizer": mock_anonymizer,
            "redis": mock_redis,
            "redis_storage": redis_storage
        }
