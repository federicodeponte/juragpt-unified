"""Test Gemini client with mocked API calls"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from app.core.gemini_client import GeminiClient, GeminiAPIError


class TestGeminiClient:
    """Test Gemini API client"""

    @pytest.fixture
    def mock_gemini_response(self):
        """Mock Gemini API response"""
        mock_response = Mock()
        mock_response.text = "According to §5.2: Die Kündigungsfrist beträgt 3 Monate."
        mock_response.usage_metadata = Mock()
        mock_response.usage_metadata.prompt_token_count = 100
        mock_response.usage_metadata.candidates_token_count = 50
        return mock_response

    @pytest.fixture
    def client(self):
        """Create client with mock API key"""
        with patch("google.generativeai.configure"):
            with patch("google.generativeai.GenerativeModel"):
                return GeminiClient(api_key="test-key")

    def test_analyze_with_mock(self, client, mock_gemini_response):
        """Test analysis with mocked API"""
        client.model.generate_content = Mock(return_value=mock_gemini_response)

        result = client.analyze(
            query="Was ist die Kündigungsfrist?",
            context="§5.2 Die Kündigungsfrist beträgt 3 Monate.",
            request_id="test-123",
        )

        # Should call generate_content
        assert client.model.generate_content.called

        # Should return structured response
        assert "answer" in result
        assert "latency_ms" in result
        assert "tokens_used" in result

        # Answer should contain response text
        assert "Kündigungsfrist" in result["answer"]

        # Tokens should be counted
        assert result["tokens_used"] == 150  # 100 + 50

    def test_cite_first_prompt(self, client):
        """Test that prompt enforces cite-first pattern"""
        query = "What is the termination period?"
        context = "§5.2 Termination period is 3 months."

        # Mock to capture the prompt
        mock_response = Mock()
        mock_response.text = "Response"
        mock_response.usage_metadata = Mock()
        mock_response.usage_metadata.prompt_token_count = 50
        mock_response.usage_metadata.candidates_token_count = 20
        client.model.generate_content = Mock(return_value=mock_response)

        client.analyze(query, context)

        # Get the actual prompt sent
        call_args = client.model.generate_content.call_args
        actual_prompt = call_args[0][0]

        # Prompt should emphasize citations
        assert "cite" in actual_prompt.lower() or "§" in actual_prompt
        assert context in actual_prompt
        assert query in actual_prompt

    def test_api_error_handling(self, client):
        """Test API error handling"""
        client.model.generate_content = Mock(side_effect=Exception("API Error"))

        with pytest.raises(GeminiAPIError):
            client.analyze("query", "context")

    def test_verify_answer(self, client):
        """Test answer verification"""
        mock_verification = Mock()
        mock_verification.text = "✓ All statements supported"

        client.model.generate_content = Mock(return_value=mock_verification)

        result = client.verify_answer(answer="According to §5: something", context="§5 something")

        assert "is_supported" in result
        assert result["is_supported"] is True

    def test_verify_unsupported_answer(self, client):
        """Test verification detects unsupported claims"""
        mock_verification = Mock()
        mock_verification.text = "- Unsupported claim 1: xyz"

        client.model.generate_content = Mock(return_value=mock_verification)

        result = client.verify_answer(answer="According to §5: xyz", context="§5 abc")

        assert result["is_supported"] is False

    def test_empty_response_handling(self, client):
        """Test handling of empty API response"""
        mock_response = Mock()
        mock_response.text = None
        mock_response.usage_metadata = Mock()
        mock_response.usage_metadata.prompt_token_count = 10
        mock_response.usage_metadata.candidates_token_count = 0

        client.model.generate_content = Mock(return_value=mock_response)

        result = client.analyze("query", "context")

        # Should handle empty response gracefully
        assert result["answer"] == ""
