"""
Test local LLM verifier using Ollama
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import httpx
from app.core.local_verifier import LocalVerifier, OllamaError


class TestLocalVerifier:
    """Test Ollama-based local verification"""

    def test_verifier_initialization_available(self):
        """Test verifier initialization when Ollama is available"""
        with patch("app.core.local_verifier.httpx.Client") as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_client.return_value.__enter__.return_value.get.return_value = mock_response

            verifier = LocalVerifier()

            assert verifier.available is True
            assert verifier.model == "mistral:7b"
            assert verifier.ollama_endpoint == "http://localhost:11434"

    def test_verifier_initialization_unavailable(self):
        """Test verifier initialization when Ollama is unavailable"""
        with patch("app.core.local_verifier.httpx.Client") as mock_client:
            mock_client.return_value.__enter__.return_value.get.side_effect = httpx.ConnectError(
                "Connection refused"
            )

            verifier = LocalVerifier()

            assert verifier.available is False

    def test_verify_answer_all_supported(self):
        """Test verification when all statements are supported"""
        answer = "According to §1: The contract is valid."
        context = "§1: The contract is valid and binding."

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"response": "✓ All statements supported"}

        with patch("app.core.local_verifier.httpx.Client") as mock_client:
            mock_client.return_value.__enter__.return_value.post.return_value = mock_response
            mock_client.return_value.__enter__.return_value.get.return_value.status_code = 200

            verifier = LocalVerifier()
            result = verifier.verify_answer(answer, context, "test-123")

            assert result["is_supported"] is True
            assert "All statements supported" in result["verification_details"]

    def test_verify_answer_unsupported_claims(self):
        """Test verification when claims are unsupported"""
        answer = "According to §1: The contract expires in 2030."
        context = "§1: The contract is valid and binding."

        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "response": "- Unsupported: The contract expires in 2030"
        }

        with patch("app.core.local_verifier.httpx.Client") as mock_client:
            mock_client.return_value.__enter__.return_value.post.return_value = mock_response
            mock_client.return_value.__enter__.return_value.get.return_value.status_code = 200

            verifier = LocalVerifier()
            result = verifier.verify_answer(answer, context, "test-456")

            assert result["is_supported"] is False
            assert "Unsupported" in result["verification_details"]

    def test_verify_answer_ollama_unavailable(self):
        """Test verification fallback when Ollama is unavailable"""
        with patch("app.core.local_verifier.httpx.Client") as mock_client:
            mock_client.return_value.__enter__.return_value.get.side_effect = httpx.ConnectError(
                "Connection refused"
            )

            verifier = LocalVerifier()
            result = verifier.verify_answer("Some answer", "Some context", "test-789")

            # Should fail open
            assert result["is_supported"] is True
            assert "unavailable" in result["verification_details"].lower()

    def test_verify_answer_http_error(self):
        """Test verification handling HTTP errors"""
        mock_get_response = Mock()
        mock_get_response.status_code = 200

        mock_post_response = Mock()
        mock_post_response.raise_for_status.side_effect = httpx.HTTPError("Server error")

        with patch("app.core.local_verifier.httpx.Client") as mock_client:
            mock_context = mock_client.return_value.__enter__.return_value
            mock_context.get.return_value = mock_get_response
            mock_context.post.return_value = mock_post_response

            verifier = LocalVerifier()
            result = verifier.verify_answer("Some answer", "Some context", "test-error")

            # Should fail open on errors
            assert result["is_supported"] is True
            assert "error" in result["verification_details"].lower()

    def test_build_verification_prompt(self):
        """Test verification prompt construction"""
        verifier = LocalVerifier()

        answer = "According to §5: Parties must give 30 days notice."
        context = "§5: Either party may terminate with 30 days notice."

        prompt = verifier._build_verification_prompt(answer, context)

        assert "fact-checker" in prompt.lower()
        assert answer in prompt
        assert context in prompt
        assert "CONTEXT:" in prompt
        assert "ANSWER:" in prompt

    def test_parse_verification_result_supported(self):
        """Test parsing supported verification result"""
        verifier = LocalVerifier()

        result = "✓ All statements supported"
        is_supported = verifier._parse_verification_result(result)

        assert is_supported is True

    def test_parse_verification_result_unsupported(self):
        """Test parsing unsupported verification result"""
        verifier = LocalVerifier()

        result = "- Unsupported: The contract value is €1M"
        is_supported = verifier._parse_verification_result(result)

        assert is_supported is False

    def test_parse_verification_result_ambiguous(self):
        """Test parsing ambiguous verification result (default to supported)"""
        verifier = LocalVerifier()

        result = "The answer seems reasonable but cannot be fully verified."
        is_supported = verifier._parse_verification_result(result)

        # Should default to True for unclear results
        assert is_supported is True

    def test_custom_endpoint_and_model(self):
        """Test verifier with custom endpoint and model"""
        with patch("app.core.local_verifier.httpx.Client") as mock_client:
            mock_response = Mock()
            mock_response.status_code = 200
            mock_client.return_value.__enter__.return_value.get.return_value = mock_response

            verifier = LocalVerifier(
                ollama_endpoint="http://custom:8080", model="llama2:13b", timeout=60
            )

            assert verifier.ollama_endpoint == "http://custom:8080"
            assert verifier.model == "llama2:13b"
            assert verifier.timeout == 60

    def test_verify_answer_request_structure(self):
        """Test that verification sends correct request to Ollama"""
        mock_get_response = Mock()
        mock_get_response.status_code = 200

        mock_post_response = Mock()
        mock_post_response.status_code = 200
        mock_post_response.json.return_value = {"response": "✓ All statements supported"}

        with patch("app.core.local_verifier.httpx.Client") as mock_client:
            mock_context = mock_client.return_value.__enter__.return_value
            mock_context.get.return_value = mock_get_response
            mock_context.post.return_value = mock_post_response

            verifier = LocalVerifier()
            verifier.verify_answer("Test answer", "Test context", "req-123")

            # Verify POST was called with correct structure
            post_call_args = mock_context.post.call_args
            assert post_call_args[0][0] == "http://localhost:11434/api/generate"

            json_data = post_call_args[1]["json"]
            assert json_data["model"] == "mistral:7b"
            assert json_data["stream"] is False
            assert "prompt" in json_data
            assert json_data["options"]["temperature"] == 0.1


class TestLocalVerifierIntegration:
    """Integration tests for local verifier"""

    def test_verifier_with_realistic_legal_text(self):
        """Test verifier with realistic German legal content"""
        answer = """According to §312 BGB Absatz 1: Bei einem Fernabsatzvertrag steht dem
        Verbraucher ein Widerrufsrecht zu."""

        context = """§312 BGB - Widerrufsrecht

Absatz 1: Bei einem Fernabsatzvertrag steht dem Verbraucher ein Widerrufsrecht nach
§355 zu.

Absatz 2: Die Widerrufsfrist beträgt 14 Tage."""

        mock_get_response = Mock()
        mock_get_response.status_code = 200

        mock_post_response = Mock()
        mock_post_response.status_code = 200
        mock_post_response.json.return_value = {"response": "✓ All statements supported"}

        with patch("app.core.local_verifier.httpx.Client") as mock_client:
            mock_context = mock_client.return_value.__enter__.return_value
            mock_context.get.return_value = mock_get_response
            mock_context.post.return_value = mock_post_response

            verifier = LocalVerifier()
            result = verifier.verify_answer(answer, context)

            assert result["is_supported"] is True
