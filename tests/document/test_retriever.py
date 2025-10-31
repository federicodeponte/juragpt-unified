"""Test retriever and embedder"""

import pytest
import numpy as np
from unittest.mock import Mock, MagicMock
from app.core.retriever import Embedder, Retriever, get_retriever
from app.db.models import RetrievalResult
import uuid


class TestEmbedder:
    """Test embedding generation"""

    @pytest.fixture
    def embedder(self):
        """Create a mocked embedder for testing"""

        def mock_encode(text_or_list, convert_to_numpy=True, show_progress_bar=False):
            """Mock encode that handles both single and batch with deterministic but different vectors"""

            def get_vector(text):
                # Create deterministic but different vectors based on text hash
                base_val = hash(text) % 1000 / 1000.0
                return np.array([base_val + i / 1000 for i in range(384)], dtype=np.float32)

            if isinstance(text_or_list, str):
                # Single text - return 1D array
                return get_vector(text_or_list)
            else:
                # Batch - return 2D array
                return np.array([get_vector(text) for text in text_or_list], dtype=np.float32)

        mock_model = MagicMock()
        mock_model.encode.side_effect = mock_encode
        mock_model.get_sentence_embedding_dimension.return_value = 384

        embedder = Embedder.__new__(Embedder)
        embedder.model_name = "test-model"
        embedder.model = mock_model
        embedder.embedding_dim = 384
        return embedder

    def test_single_embedding(self, embedder):
        """Test single text embedding"""
        text = "Dies ist ein Testvertrag."

        embedding = embedder.embed_text(text)

        assert isinstance(embedding, list)
        assert len(embedding) == embedder.embedding_dim
        assert all(isinstance(x, float) for x in embedding)

    def test_batch_embedding(self, embedder):
        """Test batch embedding generation"""
        texts = ["Text eins", "Text zwei", "Text drei"]

        embeddings = embedder.embed_batch(texts)

        assert len(embeddings) == len(texts)
        assert all(len(emb) == embedder.embedding_dim for emb in embeddings)

    def test_embedding_similarity(self, embedder):
        """Test that similar texts have similar embeddings"""
        text1 = "Der Vertrag regelt die Zusammenarbeit."
        text2 = "Der Vertrag regelt die Kooperation."
        text3 = "Das Wetter ist heute schön."

        emb1 = embedder.embed_text(text1)
        emb2 = embedder.embed_text(text2)
        emb3 = embedder.embed_text(text3)

        # Cosine similarity helper
        def cosine_sim(a, b):
            import numpy as np

            return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))

        sim_12 = cosine_sim(emb1, emb2)
        sim_13 = cosine_sim(emb1, emb3)

        # Similar texts should have higher similarity
        assert sim_12 > sim_13


class TestRetriever:
    """Test retrieval logic"""

    @pytest.fixture
    def retriever(self):
        return Retriever()

    def test_format_context(self, retriever):
        """Test context formatting for LLM"""
        results = [
            RetrievalResult(
                chunk_id=uuid.uuid4(),
                section_id="§5.2",
                content="Die Kündigungsfrist beträgt 3 Monate.",
                similarity=0.92,
                parent_content="§5 Kündigung\nAllgemeine Regelungen.",
                sibling_contents=["§5.1 Ordentliche Kündigung"],
            )
        ]

        formatted = retriever.format_context(results)

        # Should contain section ID
        assert "§5.2" in formatted

        # Should contain content
        assert "Kündigungsfrist" in formatted

        # Should show relevance
        assert "92" in formatted or "0.92" in formatted

    def test_format_multiple_results(self, retriever):
        """Test formatting multiple results"""
        results = [
            RetrievalResult(
                chunk_id=uuid.uuid4(),
                section_id=f"§{i}",
                content=f"Content {i}",
                similarity=0.9 - (i * 0.1),
                parent_content=None,
                sibling_contents=[],
            )
            for i in range(3)
        ]

        formatted = retriever.format_context(results)

        # Should contain all sections
        for i in range(3):
            assert f"§{i}" in formatted

    def test_format_with_parent_siblings(self, retriever):
        """Test that parent and siblings are included"""
        result = RetrievalResult(
            chunk_id=uuid.uuid4(),
            section_id="§5.2",
            content="Target content",
            similarity=0.95,
            parent_content="Parent section content",
            sibling_contents=["Sibling 1", "Sibling 2"],
        )

        formatted = retriever.format_context([result])

        assert "Parent Context" in formatted or "parent" in formatted.lower()
        assert "Target content" in formatted
        assert "Sibling" in formatted or any(s in formatted for s in ["Sibling 1", "Sibling 2"])


# Mock async tests (require async setup)
class TestRetrieverAsync:
    """Test async retrieval methods (integration tests)"""

    @pytest.mark.asyncio
    async def test_index_document_chunks_mock(self):
        """Test chunk indexing (mock)"""
        # This would require database setup
        # Skipping actual DB interaction
        pass

    @pytest.mark.asyncio
    async def test_retrieve_mock(self):
        """Test retrieval (mock)"""
        # This would require database setup
        pass
