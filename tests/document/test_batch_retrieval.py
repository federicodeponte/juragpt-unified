"""
Tests for batch context retrieval (N+1 optimization)
Phase 16: Fix N+1 query patterns
"""

import pytest
import uuid
from unittest.mock import AsyncMock, Mock, patch
from app.db.supabase_client import SupabaseClient


class TestBatchContextRetrieval:
    """Test batch context retrieval for N+1 optimization"""

    @pytest.fixture
    def supabase_client(self):
        """Create mocked Supabase client"""
        with patch("app.db.supabase_client.create_client"):
            client = SupabaseClient()
            client.client = Mock()
            return client

    @pytest.mark.asyncio
    async def test_get_context_chunks_batch_single_chunk(self, supabase_client):
        """Test batch retrieval with single chunk"""
        chunk_id = uuid.uuid4()

        # Mock RPC response
        mock_response = Mock()
        mock_response.data = [
            {
                "chunk_id": str(chunk_id),
                "id": str(chunk_id),
                "section_id": "§5",
                "content": "Target content",
                "chunk_type": "section",
                "relation": "target"
            },
            {
                "chunk_id": str(chunk_id),
                "id": str(uuid.uuid4()),
                "section_id": "§4",
                "content": "Parent content",
                "chunk_type": "section",
                "relation": "parent"
            }
        ]

        supabase_client.client.rpc.return_value.execute.return_value = mock_response

        result = await supabase_client.get_context_chunks_batch([chunk_id])

        assert chunk_id in result
        assert result[chunk_id]["target"] is not None
        assert result[chunk_id]["parent"] is not None
        assert result[chunk_id]["target"]["content"] == "Target content"
        assert result[chunk_id]["parent"]["content"] == "Parent content"

    @pytest.mark.asyncio
    async def test_get_context_chunks_batch_multiple_chunks(self, supabase_client):
        """Test batch retrieval with multiple chunks"""
        chunk_id_1 = uuid.uuid4()
        chunk_id_2 = uuid.uuid4()

        # Mock RPC response with data for 2 chunks
        mock_response = Mock()
        mock_response.data = [
            # Chunk 1
            {
                "chunk_id": str(chunk_id_1),
                "id": str(chunk_id_1),
                "section_id": "§5",
                "content": "Content 1",
                "chunk_type": "section",
                "relation": "target"
            },
            # Chunk 2
            {
                "chunk_id": str(chunk_id_2),
                "id": str(chunk_id_2),
                "section_id": "§6",
                "content": "Content 2",
                "chunk_type": "section",
                "relation": "target"
            }
        ]

        supabase_client.client.rpc.return_value.execute.return_value = mock_response

        result = await supabase_client.get_context_chunks_batch([chunk_id_1, chunk_id_2])

        assert len(result) == 2
        assert chunk_id_1 in result
        assert chunk_id_2 in result
        assert result[chunk_id_1]["target"]["content"] == "Content 1"
        assert result[chunk_id_2]["target"]["content"] == "Content 2"

    @pytest.mark.asyncio
    async def test_get_context_chunks_batch_with_siblings(self, supabase_client):
        """Test batch retrieval includes siblings"""
        chunk_id = uuid.uuid4()
        sibling_id_1 = uuid.uuid4()
        sibling_id_2 = uuid.uuid4()

        # Mock RPC response with target, parent, and siblings
        mock_response = Mock()
        mock_response.data = [
            {
                "chunk_id": str(chunk_id),
                "id": str(chunk_id),
                "section_id": "§5.1",
                "content": "Target",
                "chunk_type": "subsection",
                "relation": "target"
            },
            {
                "chunk_id": str(chunk_id),
                "id": str(sibling_id_1),
                "section_id": "§5.2",
                "content": "Sibling 1",
                "chunk_type": "subsection",
                "relation": "sibling"
            },
            {
                "chunk_id": str(chunk_id),
                "id": str(sibling_id_2),
                "section_id": "§5.3",
                "content": "Sibling 2",
                "chunk_type": "subsection",
                "relation": "sibling"
            }
        ]

        supabase_client.client.rpc.return_value.execute.return_value = mock_response

        result = await supabase_client.get_context_chunks_batch([chunk_id])

        assert result[chunk_id]["target"]["content"] == "Target"
        assert len(result[chunk_id]["siblings"]) == 2
        assert result[chunk_id]["siblings"][0]["content"] == "Sibling 1"
        assert result[chunk_id]["siblings"][1]["content"] == "Sibling 2"

    @pytest.mark.asyncio
    async def test_get_context_chunks_batch_empty_list(self, supabase_client):
        """Test batch retrieval with empty chunk list"""
        result = await supabase_client.get_context_chunks_batch([])

        assert result == {}
        # RPC should not be called for empty list
        supabase_client.client.rpc.assert_not_called()

    @pytest.mark.asyncio
    async def test_get_context_chunks_batch_initializes_structure(self, supabase_client):
        """Test batch retrieval initializes proper structure"""
        chunk_id = uuid.uuid4()

        # Mock response with only target (no parent/siblings)
        mock_response = Mock()
        mock_response.data = [
            {
                "chunk_id": str(chunk_id),
                "id": str(chunk_id),
                "section_id": "§5",
                "content": "Target",
                "chunk_type": "section",
                "relation": "target"
            }
        ]

        supabase_client.client.rpc.return_value.execute.return_value = mock_response

        result = await supabase_client.get_context_chunks_batch([chunk_id])

        # Should have initialized structure with None parent and empty siblings
        assert result[chunk_id]["target"] is not None
        assert result[chunk_id]["parent"] is None
        assert result[chunk_id]["siblings"] == []
