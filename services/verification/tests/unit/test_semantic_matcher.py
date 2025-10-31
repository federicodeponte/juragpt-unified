# -*- coding: utf-8 -*-
"""
Unit tests for SemanticMatcher module.
"""

import pytest
import numpy as np
from auditor.core.semantic_matcher import SemanticMatcher


class TestSemanticMatcher:
    """Test SemanticMatcher functionality."""

    @pytest.fixture
    def matcher(self):
        """Create matcher with small model for testing."""
        return SemanticMatcher(
            model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
            device="cpu",
            cache_enabled=False,  # Disable cache for predictable tests
        )

    @pytest.fixture
    def cached_matcher(self):
        """Create matcher with caching enabled."""
        return SemanticMatcher(
            model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
            device="cpu",
            cache_enabled=True,
            cache_size=10,
        )

    def test_initialization(self):
        """Test matcher initialization."""
        matcher = SemanticMatcher(
            model_name="test-model",
            device="cpu",
            cache_enabled=True,
            cache_size=100,
        )
        assert matcher.model_name == "test-model"
        assert matcher.device == "cpu"
        assert matcher.cache_enabled is True
        assert matcher.cache_size == 100
        assert matcher._model is None  # Lazy loading

    def test_lazy_loading(self, matcher):
        """Test model lazy loading."""
        # Model should not be loaded initially
        assert matcher._model is None

        # Access model property triggers loading
        model = matcher.model
        assert model is not None
        assert matcher._model is not None

        # Second access returns same model
        model2 = matcher.model
        assert model is model2

    def test_hash_text(self, matcher):
        """Test text hashing for cache keys."""
        text = "Test sentence for hashing"
        hash1 = matcher._hash_text(text)

        # Should return consistent hash
        assert isinstance(hash1, str)
        assert len(hash1) == 16  # Truncated to 16 chars

        # Same text should produce same hash
        hash2 = matcher._hash_text(text)
        assert hash1 == hash2

        # Different text should produce different hash
        hash3 = matcher._hash_text("Different text")
        assert hash1 != hash3

    @pytest.mark.slow
    def test_encode_single_text(self, matcher):
        """Test encoding single text to embedding."""
        text = "Dies ist ein Testsatz."
        embedding = matcher.encode(text, use_cache=False)

        # Should return numpy array
        assert isinstance(embedding, np.ndarray)
        assert len(embedding.shape) == 1  # 1D array
        assert embedding.shape[0] > 0  # Has dimensions

    @pytest.mark.slow
    def test_encode_with_cache(self, cached_matcher):
        """Test embedding caching."""
        text = "Test sentence for caching"

        # First encoding should cache
        emb1 = cached_matcher.encode(text, use_cache=True)
        assert len(cached_matcher._embedding_cache) == 1

        # Second encoding should use cache
        emb2 = cached_matcher.encode(text, use_cache=True)
        assert len(cached_matcher._embedding_cache) == 1

        # Embeddings should be identical (same object from cache)
        np.testing.assert_array_equal(emb1, emb2)

    @pytest.mark.slow
    def test_cache_lru_eviction(self, cached_matcher):
        """Test LRU cache eviction."""
        # Fill cache beyond limit
        for i in range(15):  # cache_size is 10
            cached_matcher.encode(f"Test sentence number {i}", use_cache=True)

        # Cache should be at limit
        assert len(cached_matcher._embedding_cache) == cached_matcher.cache_size

    @pytest.mark.slow
    def test_encode_batch(self, matcher):
        """Test batch encoding."""
        texts = [
            "Erster Testsatz hier.",
            "Zweiter Testsatz mit anderen Wörtern.",
            "Dritter Satz für den Test.",
        ]
        embeddings = matcher.encode_batch(texts)

        # Should return 2D array
        assert isinstance(embeddings, np.ndarray)
        assert len(embeddings.shape) == 2
        assert embeddings.shape[0] == len(texts)  # One embedding per text

    @pytest.mark.slow
    def test_compute_similarity(self, matcher):
        """Test similarity computation between two texts."""
        text1 = "Der Schuldner haftet für Schäden."
        text2 = "Der Schuldner ist für Schäden verantwortlich."
        text3 = "Das Wetter ist heute schön."

        # Similar texts should have high similarity
        sim_high = matcher.compute_similarity(text1, text2)
        assert isinstance(sim_high, float)
        assert 0.0 <= sim_high <= 1.0
        assert sim_high > 0.5  # Should be somewhat similar

        # Dissimilar texts should have lower similarity
        sim_low = matcher.compute_similarity(text1, text3)
        assert sim_low < sim_high

    @pytest.mark.slow
    def test_find_best_match(self, matcher):
        """Test finding best matching candidate."""
        query = "Der Schuldner haftet für den Schaden."
        candidates = [
            "Der Verkäufer übergibt die Sache.",
            "Wer fahrlässig einen Schaden verursacht, haftet dafür.",
            "Das Wetter ist schön heute.",
        ]

        matches = matcher.find_best_match(query, candidates, top_k=2)

        # Should return list of (index, score) tuples
        assert isinstance(matches, list)
        assert len(matches) == 2  # top_k=2

        # Each match should be (index, score)
        for idx, score in matches:
            assert isinstance(idx, int)
            assert isinstance(score, float)
            assert 0 <= idx < len(candidates)
            assert 0.0 <= score <= 1.0

        # Best match should be candidate[1] (about liability)
        best_idx, best_score = matches[0]
        assert best_idx == 1

        # Scores should be in descending order
        assert matches[0][1] >= matches[1][1]

    @pytest.mark.slow
    def test_find_best_match_empty_candidates(self, matcher):
        """Test finding best match with empty candidates."""
        query = "Test query"
        candidates = []

        matches = matcher.find_best_match(query, candidates)
        assert matches == []

    @pytest.mark.slow
    def test_verify_sentence(self, matcher):
        """Test sentence verification against sources."""
        sentence = "Der Schuldner haftet für vorsätzliche Schäden."
        sources = [
            "Wer vorsätzlich oder fahrlässig einen Schaden verursacht, haftet dafür.",
            "Der Verkäufer übergibt dem Käufer die Sache.",
        ]

        result = matcher.verify_sentence(sentence, sources, threshold=0.5)

        # Check result structure
        assert "verified" in result
        assert "max_score" in result
        assert "best_match_idx" in result
        assert "best_match_text" in result
        assert "all_scores" in result

        # Check types
        assert isinstance(result["verified"], bool)
        assert isinstance(result["max_score"], float)
        assert isinstance(result["best_match_idx"], int)
        assert isinstance(result["best_match_text"], str)
        assert isinstance(result["all_scores"], list)

        # Best match should be source[0] (about liability)
        assert result["best_match_idx"] == 0
        assert result["best_match_text"] == sources[0]

    @pytest.mark.slow
    def test_verify_sentence_empty_sources(self, matcher):
        """Test sentence verification with no sources."""
        sentence = "Test sentence"
        sources = []

        result = matcher.verify_sentence(sentence, sources)

        assert result["verified"] is False
        assert result["max_score"] == 0.0
        assert result["best_match_idx"] is None
        assert result["best_match_text"] is None
        assert result["all_scores"] == []

    @pytest.mark.slow
    def test_verify_sentence_threshold(self, matcher):
        """Test verification threshold logic."""
        sentence = "Der Schuldner haftet."
        sources = [
            "Wer vorsätzlich einen Schaden verursacht, haftet dafür.",
        ]

        # Low threshold should verify
        result_low = matcher.verify_sentence(sentence, sources, threshold=0.3)
        assert result_low["verified"] is True

        # Very high threshold might not verify
        result_high = matcher.verify_sentence(sentence, sources, threshold=0.99)
        # This depends on actual similarity, so we just check it's a bool
        assert isinstance(result_high["verified"], bool)

    @pytest.mark.slow
    def test_verify_answer(self, matcher):
        """Test full answer verification."""
        sentences = [
            "Der Schuldner haftet für Schäden.",
            "Das Wetter ist heute schön.",
            "Vorsätzliches Verhalten wird bestraft.",
        ]
        sources = [
            "Wer vorsätzlich oder fahrlässig einen Schaden verursacht, haftet dafür.",
            "Vorsatz liegt vor, wenn der Täter den Erfolg wollte.",
        ]

        result = matcher.verify_answer(sentences, sources, sentence_threshold=0.5)

        # Check result structure
        assert "verified_count" in result
        assert "total_count" in result
        assert "verification_rate" in result
        assert "sentences" in result
        assert "overall_confidence" in result

        # Check values
        assert result["total_count"] == len(sentences)
        assert 0 <= result["verified_count"] <= result["total_count"]
        assert 0.0 <= result["verification_rate"] <= 1.0
        assert len(result["sentences"]) == len(sentences)
        assert 0.0 <= result["overall_confidence"] <= 1.0

        # Each sentence result should have required fields
        for sent_result in result["sentences"]:
            assert "verified" in sent_result
            assert "max_score" in sent_result
            assert "sentence_text" in sent_result

    @pytest.mark.slow
    def test_verify_answer_empty(self, matcher):
        """Test verifying empty answer."""
        result = matcher.verify_answer([], [])

        assert result["verified_count"] == 0
        assert result["total_count"] == 0
        assert result["verification_rate"] == 0.0
        assert result["sentences"] == []
        assert result["overall_confidence"] == 0.0

    def test_get_cache_stats(self, cached_matcher):
        """Test cache statistics retrieval."""
        stats = cached_matcher.get_cache_stats()

        assert "cache_enabled" in stats
        assert "cache_size" in stats
        assert "cache_limit" in stats
        assert "cache_usage_pct" in stats

        assert stats["cache_enabled"] is True
        assert stats["cache_limit"] == 10
        assert isinstance(stats["cache_size"], int)
        assert isinstance(stats["cache_usage_pct"], float)

    @pytest.mark.slow
    def test_clear_cache(self, cached_matcher):
        """Test cache clearing."""
        # Add some items to cache
        cached_matcher.encode("Test 1", use_cache=True)
        cached_matcher.encode("Test 2", use_cache=True)
        assert len(cached_matcher._embedding_cache) > 0

        # Clear cache
        cached_matcher.clear_cache()
        assert len(cached_matcher._embedding_cache) == 0

    def test_cache_disabled(self, matcher):
        """Test that caching can be disabled."""
        assert matcher.cache_enabled is False

        # Encoding should not add to cache
        matcher.encode("Test", use_cache=True)
        assert len(matcher._embedding_cache) == 0
