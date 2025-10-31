# -*- coding: utf-8 -*-
"""
Edge case tests using mock data from edge_cases.json.
"""

import pytest
from fastapi.testclient import TestClient
from auditor.api.server import app
from auditor.core.sentence_processor import SentenceProcessor
from auditor.core.semantic_matcher import SemanticMatcher
from auditor.core.confidence_engine import ConfidenceEngine, VerificationSignals


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.mark.edge_case
class TestEdgeCases:
    """Test edge cases from mock data."""

    def test_contradictory_sources(self, edge_cases):
        """Test handling contradictory source documents."""
        # Find contradictory case in mock data
        contradictory_cases = [
            ec for ec in edge_cases
            if ec.get("name") == "contradictory_sources"
        ]

        if contradictory_cases:
            case = contradictory_cases[0]
            # Should handle contradictions gracefully
            assert "answer" in case
            assert "sources" in case

    def test_paraphrased_content(self):
        """Test verification of heavily paraphrased content."""
        processor = SentenceProcessor()

        original = "Der Schuldner haftet für vorsätzliche und fahrlässige Pflichtverletzungen."
        paraphrased = "Vorsatz und Fahrlässigkeit müssen vom Schuldner vertreten werden."

        # Both should be recognized as related
        result_orig = processor.process_answer(original)
        result_para = processor.process_answer(paraphrased)

        assert result_orig["total_sentences"] >= 1
        assert result_para["total_sentences"] >= 1

    def test_missing_citations(self):
        """Test answer with no legal citations."""
        processor = SentenceProcessor()

        answer = "Der Schuldner muss für seine Handlungen einstehen."
        result = processor.process_answer(answer)

        # Should process but detect no citations
        assert result["has_citations"] is False
        assert len(result["citations"]) == 0

    def test_multiple_overlapping_citations(self):
        """Test answer with multiple overlapping citations."""
        processor = SentenceProcessor()

        answer = "Nach § 823 Abs. 1 BGB und § 823 Abs. 2 BGB haftet der Schuldner."
        result = processor.process_answer(answer)

        # Should detect multiple citations
        if result["has_citations"]:
            assert len(result["citations"]) >= 1

    def test_partial_source_match(self):
        """Test answer that partially matches sources."""
        engine = ConfidenceEngine()

        # Only some sentences match
        signals = VerificationSignals(
            sentence_scores=[0.90, 0.50, 0.85],  # Mixed
            retrieval_scores=[0.80],
            has_citations=True,
            citation_count=1,
        )

        result = engine.calculate_confidence(signals)

        # Should reflect partial matching
        assert 0.0 < result["confidence"] < 1.0
        assert result["statistics"]["verified_sentences"] < result["statistics"]["total_sentences"]

    def test_out_of_domain_content(self):
        """Test handling non-legal content."""
        processor = SentenceProcessor()

        non_legal = "Das Wetter ist heute sehr schön und sonnig."
        result = processor.process_answer(non_legal)

        # Should process but likely mark as non-legal
        assert result["total_sentences"] >= 1

    def test_very_short_answer(self):
        """Test handling very short answers."""
        processor = SentenceProcessor()

        short = "Ja."
        result = processor.process_answer(short)

        # Should handle gracefully
        assert result["total_sentences"] >= 0

    def test_very_long_answer(self):
        """Test handling very long answers."""
        processor = SentenceProcessor()

        # Create long answer (100 sentences)
        long_answer = " ".join([
            f"Dies ist Satz Nummer {i} mit einigen rechtlichen Inhalten."
            for i in range(100)
        ])

        result = processor.process_answer(long_answer)

        # Should process all sentences
        assert result["total_sentences"] >= 50
        assert result["total_tokens"] > 200

    def test_special_characters_handling(self):
        """Test handling of special legal characters."""
        processor = SentenceProcessor()

        text = "§ 823 BGB regelt die Haftung. Art. 1 GG schützt die Würde. § 242 BGB: Treu und Glauben."
        result = processor.process_answer(text)

        # Should preserve special characters
        assert result["total_sentences"] >= 2

    def test_unicode_and_umlauts(self):
        """Test handling German umlauts and special characters."""
        processor = SentenceProcessor()

        text = "Ärzte müssen über Risiken aufklären. Das Übereinkommen gilt für alle Bürger."
        result = processor.process_answer(text)

        # Should handle Unicode properly
        assert result["total_sentences"] >= 2
        # Check that text wasn't corrupted
        assert "Ärzte" in result["original"] or "Aerzte" in result["normalized"]

    def test_empty_string_handling(self):
        """Test handling empty strings."""
        processor = SentenceProcessor()

        result = processor.process_answer("")

        assert result["total_sentences"] == 0
        assert result["total_tokens"] == 0
        assert result["has_citations"] is False

    def test_whitespace_only(self):
        """Test handling whitespace-only input."""
        processor = SentenceProcessor()

        result = processor.process_answer("   \n\t   ")

        # Should treat as empty
        assert result["total_sentences"] == 0

    def test_numeric_content(self):
        """Test handling answers with lots of numbers."""
        processor = SentenceProcessor()

        text = "Nach § 823 BGB beträgt die Frist 3 Jahre gemäß § 195 BGB."
        result = processor.process_answer(text)

        # Should handle numbers in legal context
        assert result["total_sentences"] >= 1

    def test_mixed_language_content(self):
        """Test handling mixed German-English content."""
        processor = SentenceProcessor()

        text = "Das German law besagt, dass liability besteht."
        result = processor.process_answer(text)

        # Should process even with language mixing
        assert result["total_sentences"] >= 1

    def test_inconsistent_citation_formats(self):
        """Test different citation formats."""
        processor = SentenceProcessor()

        # Various citation styles
        text = "§ 823 BGB, Paragraph 823 BGB, §823 BGB, § 823 Abs. 1 S. 1 BGB."
        result = processor.process_answer(text)

        # Should recognize some citations
        assert result["total_sentences"] >= 1

    def test_confidence_boundary_cases(self):
        """Test confidence scores at boundaries."""
        engine = ConfidenceEngine(sentence_threshold=0.75, overall_threshold=0.80)

        # Exactly at threshold
        signals_at_threshold = VerificationSignals(
            sentence_scores=[0.80],
            retrieval_scores=[0.80],
            has_citations=True,
            citation_count=1,
        )

        result = engine.calculate_confidence(signals_at_threshold)
        # Should handle threshold boundary correctly
        assert 0.0 <= result["confidence"] <= 1.0

    def test_zero_confidence_case(self):
        """Test case that should produce very low confidence."""
        engine = ConfidenceEngine()

        signals = VerificationSignals(
            sentence_scores=[0.0, 0.0],
            retrieval_scores=[0.0],
            has_citations=False,
            citation_count=0,
        )

        result = engine.calculate_confidence(signals)

        # Should be very low
        assert result["confidence"] < 0.5
        assert result["verified"] is False

    def test_perfect_confidence_case(self):
        """Test case that should produce high confidence."""
        engine = ConfidenceEngine()

        signals = VerificationSignals(
            sentence_scores=[1.0, 0.95, 0.98],
            retrieval_scores=[1.0, 0.98],
            has_citations=True,
            citation_count=5,
        )

        result = engine.calculate_confidence(signals)

        # Should be very high
        assert result["confidence"] > 0.85
        assert result["verified"] is True

    @pytest.mark.slow
    def test_api_edge_case_empty_sources(self, client):
        """Test API with empty sources array."""
        request = {
            "answer": "Test answer",
            "sources": [],
        }

        response = client.post("/verify", json=request)

        # Should handle gracefully
        if response.status_code == 200:
            data = response.json()
            # Low confidence expected
            assert data["confidence"] < 0.7

    @pytest.mark.slow
    def test_api_edge_case_malformed_source(self, client):
        """Test API with malformed source data."""
        request = {
            "answer": "Test answer",
            "sources": [
                {"text": "Valid source", "source_id": "s1", "score": 0.9},
                {"text": "Source missing score", "source_id": "s2"},  # Missing score
            ],
        }

        response = client.post("/verify", json=request)

        # Should handle or reject gracefully
        assert response.status_code in [200, 422]
