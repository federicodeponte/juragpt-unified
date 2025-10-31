#!/usr/bin/env python3
"""
Integration tests for JuraGPT Unified orchestrator service.

Tests the full workflow: query → retrieval → verification → response
using mocked external services.
"""

import sys
from pathlib import Path
from unittest.mock import patch, AsyncMock, MagicMock
import asyncio

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_orchestrator_unified_query_full_workflow():
    """Test complete workflow: query → retrieve → verify → response."""
    print("\nTesting orchestrator unified query workflow...")

    # Import after path setup
    from services.orchestrator.main import unified_query, QueryRequest

    # Mock httpx.AsyncClient
    with patch('services.orchestrator.main.httpx.AsyncClient') as mock_client_class:
        # Create mock client instance
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client

        # Mock retrieval service response data
        retrieval_data = {
            "sources": [
                {
                    "doc_id": "bgb_823",
                    "title": "§823 BGB - Schadensersatzpflicht",
                    "text": "Wer vorsätzlich oder fahrlässig das Leben, den Körper, die Gesundheit...",
                    "score": 0.95
                },
                {
                    "doc_id": "bgb_826",
                    "title": "§826 BGB - Sittenwidrige vorsätzliche Schädigung",
                    "text": "Wer in einer gegen die guten Sitten verstoßenden Weise...",
                    "score": 0.87
                }
            ]
        }

        # Mock verification service response data
        verification_data = {
            "confidence": 0.92,
            "trust_label": "HIGH",
            "verified_claims": 3,
            "unsupported_claims": 0
        }

        # Configure mock to return different responses based on URL
        async def mock_post(url, **kwargs):
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()

            if "retrieve" in url:
                mock_response.json = MagicMock(return_value=retrieval_data)
            elif "verify" in url:
                mock_response.json = MagicMock(return_value=verification_data)
            else:
                raise ValueError(f"Unexpected URL: {url}")

            return mock_response

        mock_client.post.side_effect = mock_post

        # Create test request
        request = QueryRequest(
            query="Wann haftet jemand nach §823 BGB?",
            top_k=2,
            answer="Eine Person haftet nach §823 BGB, wenn sie vorsätzlich oder fahrlässig...",
            verify_answer=True
        )

        # Run the async function
        async def run_test():
            result = await unified_query(request, authorization="Bearer test-token")
            return result

        response = asyncio.run(run_test())

        # Verify response structure
        assert response.query == request.query, "Query not preserved in response"
        assert len(response.sources) == 2, f"Expected 2 sources, got {len(response.sources)}"
        assert response.sources[0].doc_id == "bgb_823", "First source incorrect"
        assert response.answer == request.answer, "Answer not preserved"
        assert response.verification is not None, "Verification missing"
        assert response.verification["confidence"] == 0.92, "Verification confidence incorrect"
        assert response.verification["trust_label"] == "HIGH", "Trust label incorrect"

        print("✓ Orchestrator unified query workflow test passed")
        return True


def test_orchestrator_retrieval_only():
    """Test retrieval-only mode (no verification)."""
    print("\nTesting orchestrator retrieval-only mode...")

    from services.orchestrator.main import unified_query, QueryRequest

    with patch('services.orchestrator.main.httpx.AsyncClient') as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client

        # Mock retrieval response data
        retrieval_data = {
            "sources": [
                {"doc_id": "test_1", "title": "Test", "text": "Content", "score": 0.9}
            ]
        }

        # Configure mock response
        async def mock_post(url, **kwargs):
            mock_response = MagicMock()
            mock_response.raise_for_status = MagicMock()
            mock_response.json = MagicMock(return_value=retrieval_data)
            return mock_response

        mock_client.post.side_effect = mock_post

        # Request without answer or verification
        request = QueryRequest(
            query="Test query",
            top_k=1,
            verify_answer=False
        )

        async def run_test():
            result = await unified_query(request)
            return result

        response = asyncio.run(run_test())

        assert response.query == "Test query", "Query not preserved"
        assert len(response.sources) == 1, "Sources not returned"
        assert response.answer is None, "Answer should be None in retrieval-only mode"
        assert response.verification is None, "Verification should be None"

        print("✓ Orchestrator retrieval-only mode test passed")
        return True


def test_orchestrator_error_handling():
    """Test orchestrator handles service failures gracefully."""
    print("\nTesting orchestrator error handling...")

    from services.orchestrator.main import unified_query, QueryRequest
    from fastapi import HTTPException

    with patch('services.orchestrator.main.httpx.AsyncClient') as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client

        # Mock retrieval service failure
        mock_client.post.side_effect = Exception("Retrieval service down")

        request = QueryRequest(query="Test", top_k=5)

        async def run_test():
            try:
                await unified_query(request)
                return False  # Should have raised exception
            except HTTPException as e:
                assert e.status_code == 500, "Expected 500 status code"
                assert "Retrieval failed" in e.detail, "Error message incorrect"
                return True

        success = asyncio.run(run_test())
        assert success, "Error handling test failed"

        print("✓ Orchestrator error handling test passed")
        return True


def test_health_endpoint():
    """Test health check endpoint aggregates service status."""
    print("\nTesting orchestrator health endpoint...")

    from services.orchestrator.main import health

    with patch('services.orchestrator.main.httpx.AsyncClient') as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client

        # Mock healthy services
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_client.get.return_value = mock_response

        async def run_test():
            result = await health()
            return result

        response = asyncio.run(run_test())

        assert response["status"] == "healthy", "Overall status should be healthy"
        assert "services" in response, "Services status missing"
        assert response["services"]["retrieval"] == "healthy", "Retrieval should be healthy"
        assert response["services"]["verification"] == "healthy", "Verification should be healthy"

        print("✓ Orchestrator health endpoint test passed")
        return True


def test_health_endpoint_degraded_state():
    """Test health endpoint shows degraded state when services are down."""
    print("\nTesting orchestrator health endpoint degraded state...")

    from services.orchestrator.main import health

    with patch('services.orchestrator.main.httpx.AsyncClient') as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value.__aenter__.return_value = mock_client

        # Mock service failure
        mock_client.get.side_effect = Exception("Service unreachable")

        async def run_test():
            result = await health()
            return result

        response = asyncio.run(run_test())

        assert response["status"] == "degraded", "Overall status should be degraded"
        assert response["services"]["retrieval"] == "unreachable", "Retrieval should be unreachable"
        assert response["services"]["verification"] == "unreachable", "Verification should be unreachable"

        print("✓ Orchestrator health endpoint degraded state test passed")
        return True


def main():
    """Run all integration tests."""
    print("=" * 70)
    print("JuraGPT Unified - Orchestrator Integration Tests")
    print("=" * 70)

    tests = [
        ("Unified Query Workflow", test_orchestrator_unified_query_full_workflow),
        ("Retrieval Only Mode", test_orchestrator_retrieval_only),
        ("Error Handling", test_orchestrator_error_handling),
        ("Health Endpoint", test_health_endpoint),
        ("Health Endpoint Degraded", test_health_endpoint_degraded_state),
    ]

    results = {}
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"✗ {test_name} failed: {e}")
            results[test_name] = False

    print("\n" + "=" * 70)
    print("Integration Test Results Summary")
    print("=" * 70)

    for test_name, passed in results.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {test_name}")

    total = len(results)
    passed = sum(results.values())
    print(f"\nPassed: {passed}/{total}")

    if passed == total:
        print("\n✓ All integration tests passed!")
        return 0
    else:
        print(f"\n✗ {total - passed} integration test(s) failed")
        return 1


if __name__ == '__main__':
    sys.exit(main())
