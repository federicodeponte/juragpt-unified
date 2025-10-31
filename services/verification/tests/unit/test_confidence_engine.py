# -*- coding: utf-8 -*-
"""
Unit tests for ConfidenceEngine module.
"""

import pytest
from auditor.core.confidence_engine import ConfidenceEngine, VerificationSignals


class TestVerificationSignals:
    """Test VerificationSignals dataclass."""

    def test_initialization_minimal(self):
        """Test minimal initialization."""
        signals = VerificationSignals(
            sentence_scores=[0.9, 0.8],
            retrieval_scores=[0.95],
        )
        assert signals.sentence_scores == [0.9, 0.8]
        assert signals.retrieval_scores == [0.95]
        assert signals.has_citations is False
        assert signals.citation_count == 0
        assert signals.source_count == 0

    def test_initialization_complete(self):
        """Test full initialization."""
        signals = VerificationSignals(
            sentence_scores=[0.9, 0.8],
            retrieval_scores=[0.95, 0.90],
            has_citations=True,
            citation_count=3,
            source_count=5,
            token_overlap=0.75,
            source_diversity=0.85,
        )
        assert signals.has_citations is True
        assert signals.citation_count == 3
        assert signals.source_count == 5
        assert signals.token_overlap == 0.75
        assert signals.source_diversity == 0.85


class TestConfidenceEngine:
    """Test ConfidenceEngine functionality."""

    def test_initialization_default(self):
        """Test default initialization."""
        engine = ConfidenceEngine()
        assert engine.sentence_threshold == 0.75
        assert engine.overall_threshold == 0.80
        assert len(engine.weights) == 4
        assert sum(engine.weights.values()) == pytest.approx(1.0, abs=0.01)

    def test_initialization_custom_weights(self):
        """Test custom weights."""
        custom_weights = {
            "semantic_similarity": 0.70,
            "retrieval_quality": 0.20,
            "citation_presence": 0.05,
            "coverage": 0.05,
        }
        engine = ConfidenceEngine(weights=custom_weights)
        assert engine.weights == custom_weights

    def test_initialization_invalid_weights(self):
        """Test invalid weights raise error."""
        invalid_weights = {
            "semantic_similarity": 0.50,
            "retrieval_quality": 0.30,
            "citation_presence": 0.10,
            "coverage": 0.05,
        }  # Sum = 0.95, not 1.0
        with pytest.raises(ValueError, match="must sum to 1.0"):
            ConfidenceEngine(weights=invalid_weights)

    def test_calculate_semantic_score_empty(self):
        """Test semantic score with empty list."""
        engine = ConfidenceEngine()
        score = engine.calculate_semantic_score([])
        assert score == 0.0

    def test_calculate_semantic_score_single(self):
        """Test semantic score with single score."""
        engine = ConfidenceEngine()
        score = engine.calculate_semantic_score([0.9])
        assert 0.0 <= score <= 1.0
        # Single score should be returned as-is (minus penalties)
        assert score <= 0.9

    def test_calculate_semantic_score_high(self):
        """Test semantic score with high scores."""
        engine = ConfidenceEngine()
        scores = [0.92, 0.88, 0.90]
        score = engine.calculate_semantic_score(scores)

        # Should be high (average ~0.90)
        assert score > 0.80
        assert score <= 1.0

    def test_calculate_semantic_score_with_low_scores(self):
        """Test semantic score with some low scores."""
        engine = ConfidenceEngine()
        scores = [0.85, 0.60, 0.80]  # One score below threshold
        score = engine.calculate_semantic_score(scores)

        # Should have penalty for low score
        assert score < 0.75

    def test_calculate_semantic_score_variance_penalty(self):
        """Test variance penalty for inconsistent scores."""
        engine = ConfidenceEngine()

        # Consistent scores (low variance)
        consistent = [0.85, 0.86, 0.87]
        score_consistent = engine.calculate_semantic_score(consistent)

        # Inconsistent scores (high variance)
        inconsistent = [0.95, 0.50, 0.85]
        score_inconsistent = engine.calculate_semantic_score(inconsistent)

        # Consistent should score higher (less penalty)
        assert score_consistent > score_inconsistent

    def test_calculate_retrieval_score_empty(self):
        """Test retrieval score with empty list."""
        engine = ConfidenceEngine()
        score = engine.calculate_retrieval_score([])
        assert score == 0.5  # Neutral

    def test_calculate_retrieval_score_single(self):
        """Test retrieval score with single score."""
        engine = ConfidenceEngine()
        score = engine.calculate_retrieval_score([0.95])
        assert score == 0.95

    def test_calculate_retrieval_score_top3(self):
        """Test retrieval score uses top-3 average."""
        engine = ConfidenceEngine()
        scores = [0.95, 0.90, 0.85, 0.50, 0.40]  # Top-3: 0.95, 0.90, 0.85
        score = engine.calculate_retrieval_score(scores)

        # Should average top-3
        expected = (0.95 + 0.90 + 0.85) / 3
        assert score == pytest.approx(expected)

    def test_calculate_citation_score_none(self):
        """Test citation score with no citations."""
        engine = ConfidenceEngine()
        score = engine.calculate_citation_score(has_citations=False, citation_count=0)
        assert score == 0.3  # Neutral-low

    def test_calculate_citation_score_one(self):
        """Test citation score with one citation."""
        engine = ConfidenceEngine()
        score = engine.calculate_citation_score(has_citations=True, citation_count=1)
        assert score == 0.7

    def test_calculate_citation_score_two(self):
        """Test citation score with two citations."""
        engine = ConfidenceEngine()
        score = engine.calculate_citation_score(has_citations=True, citation_count=2)
        assert score == 0.85

    def test_calculate_citation_score_many(self):
        """Test citation score with many citations."""
        engine = ConfidenceEngine()
        score = engine.calculate_citation_score(has_citations=True, citation_count=5)

        # Should be high but <= 1.0
        assert score > 0.85
        assert score <= 1.0

    def test_calculate_coverage_score_zero(self):
        """Test coverage score with zero sentences."""
        engine = ConfidenceEngine()
        score = engine.calculate_coverage_score(verified_count=0, total_count=0)
        assert score == 0.0

    def test_calculate_coverage_score_full(self):
        """Test coverage score with full verification."""
        engine = ConfidenceEngine()
        score = engine.calculate_coverage_score(verified_count=10, total_count=10)
        assert score == 1.0

    def test_calculate_coverage_score_partial(self):
        """Test coverage score with partial verification."""
        engine = ConfidenceEngine()
        score = engine.calculate_coverage_score(verified_count=7, total_count=10)
        assert score == 0.7

    def test_calculate_confidence_high(self):
        """Test confidence calculation with high-quality signals."""
        engine = ConfidenceEngine()
        signals = VerificationSignals(
            sentence_scores=[0.92, 0.88, 0.85],
            retrieval_scores=[0.95, 0.89, 0.82],
            has_citations=True,
            citation_count=2,
            source_count=3,
        )
        result = engine.calculate_confidence(signals)

        # Check structure
        assert "confidence" in result
        assert "verified" in result
        assert "components" in result
        assert "thresholds" in result
        assert "statistics" in result

        # Should be high confidence
        assert result["confidence"] > 0.80
        assert result["verified"] is True

    def test_calculate_confidence_low(self):
        """Test confidence calculation with low-quality signals."""
        engine = ConfidenceEngine()
        signals = VerificationSignals(
            sentence_scores=[0.55, 0.48, 0.62],
            retrieval_scores=[0.60],
            has_citations=False,
            citation_count=0,
            source_count=1,
        )
        result = engine.calculate_confidence(signals)

        # Should be low confidence
        assert result["confidence"] < 0.70
        assert result["verified"] is False

    def test_calculate_confidence_components(self):
        """Test confidence components breakdown."""
        engine = ConfidenceEngine()
        signals = VerificationSignals(
            sentence_scores=[0.80, 0.85],
            retrieval_scores=[0.90],
            has_citations=True,
            citation_count=1,
            source_count=2,
        )
        result = engine.calculate_confidence(signals)

        comps = result["components"]
        assert "semantic_similarity" in comps
        assert "retrieval_quality" in comps
        assert "citation_presence" in comps
        assert "coverage" in comps

        # All components should be in [0, 1]
        for score in comps.values():
            assert 0.0 <= score <= 1.0

    def test_calculate_confidence_statistics(self):
        """Test confidence statistics."""
        engine = ConfidenceEngine(sentence_threshold=0.75)
        signals = VerificationSignals(
            sentence_scores=[0.80, 0.70, 0.85],  # 2 verified, 1 not
            retrieval_scores=[0.90],
            has_citations=True,
            citation_count=1,
        )
        result = engine.calculate_confidence(signals)

        stats = result["statistics"]
        assert stats["verified_sentences"] == 2  # 0.80 and 0.85 >= 0.75
        assert stats["total_sentences"] == 3
        assert stats["verification_rate"] == pytest.approx(2/3)

    def test_get_trust_label_verified(self):
        """Test trust label for verified confidence."""
        engine = ConfidenceEngine(overall_threshold=0.80)
        label = engine.get_trust_label(0.85)
        assert label == "✅ Verified"

    def test_get_trust_label_review(self):
        """Test trust label for review confidence."""
        engine = ConfidenceEngine(overall_threshold=0.80)
        label = engine.get_trust_label(0.70)
        assert label == "⚠️ Review"

    def test_get_trust_label_rejected(self):
        """Test trust label for rejected confidence."""
        engine = ConfidenceEngine(overall_threshold=0.80)
        label = engine.get_trust_label(0.50)
        assert label == "🚫 Rejected"

    def test_should_retry_yes(self):
        """Test retry decision for low confidence."""
        engine = ConfidenceEngine()
        assert engine.should_retry(0.50, retry_threshold=0.60) is True

    def test_should_retry_no(self):
        """Test retry decision for high confidence."""
        engine = ConfidenceEngine()
        assert engine.should_retry(0.85, retry_threshold=0.60) is False

    def test_should_retry_custom_threshold(self):
        """Test retry with custom threshold."""
        engine = ConfidenceEngine()
        assert engine.should_retry(0.65, retry_threshold=0.70) is True
        assert engine.should_retry(0.75, retry_threshold=0.70) is False

    def test_explain_confidence(self):
        """Test confidence explanation generation."""
        engine = ConfidenceEngine()
        signals = VerificationSignals(
            sentence_scores=[0.85, 0.80],
            retrieval_scores=[0.90],
            has_citations=True,
            citation_count=1,
        )
        result = engine.calculate_confidence(signals)
        explanation = engine.explain_confidence(result)

        # Should be a string
        assert isinstance(explanation, str)

        # Should contain key information
        assert "Confidence:" in explanation
        assert "Component Breakdown:" in explanation
        assert "Statistics:" in explanation
        assert "Semantic Similarity:" in explanation
        assert "Retrieval Quality:" in explanation

    def test_confidence_bounds(self):
        """Test confidence stays within [0, 1] bounds."""
        engine = ConfidenceEngine()

        # Test with extreme high scores
        signals_high = VerificationSignals(
            sentence_scores=[1.0, 1.0, 1.0],
            retrieval_scores=[1.0, 1.0],
            has_citations=True,
            citation_count=10,
        )
        result_high = engine.calculate_confidence(signals_high)
        assert 0.0 <= result_high["confidence"] <= 1.0

        # Test with extreme low scores
        signals_low = VerificationSignals(
            sentence_scores=[0.0, 0.0],
            retrieval_scores=[0.0],
            has_citations=False,
            citation_count=0,
        )
        result_low = engine.calculate_confidence(signals_low)
        assert 0.0 <= result_low["confidence"] <= 1.0

    def test_weighted_combination(self):
        """Test that weights properly combine components."""
        engine = ConfidenceEngine()
        signals = VerificationSignals(
            sentence_scores=[0.80],
            retrieval_scores=[0.90],
            has_citations=True,
            citation_count=1,
        )
        result = engine.calculate_confidence(signals)

        # Manual calculation
        comps = result["components"]
        expected = (
            comps["semantic_similarity"] * engine.weights["semantic_similarity"]
            + comps["retrieval_quality"] * engine.weights["retrieval_quality"]
            + comps["citation_presence"] * engine.weights["citation_presence"]
            + comps["coverage"] * engine.weights["coverage"]
        )

        assert result["confidence"] == pytest.approx(expected, abs=0.01)
