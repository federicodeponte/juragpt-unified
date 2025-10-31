"""Test citation verification and hallucination detection"""

import pytest
from app.core.verifier import Verifier
from app.db.models import RetrievalResult
import uuid


class TestVerifier:
    """Test verification layer"""

    @pytest.fixture
    def verifier(self):
        return Verifier()

    @pytest.fixture
    def sample_results(self):
        return [
            RetrievalResult(
                chunk_id=uuid.uuid4(),
                section_id="§5.2",
                content="Die Kündigungsfrist beträgt 3 Monate zum Quartalsende.",
                similarity=0.95,
                parent_content="§5 Kündigung",
                sibling_contents=[],
            ),
            RetrievalResult(
                chunk_id=uuid.uuid4(),
                section_id="§12",
                content="Die Haftung ist auf grobe Fahrlässigkeit beschränkt.",
                similarity=0.88,
                parent_content=None,
                sibling_contents=[],
            ),
        ]

    def test_extract_citations(self, verifier, sample_results):
        """Test citation extraction from answer"""
        answer = "According to §5.2, the notice period is 3 months. §12 limits liability."

        citations = verifier.extract_citations(answer, sample_results)

        assert len(citations) >= 2
        section_ids = [c.section_id for c in citations]
        assert "§5.2" in section_ids
        assert "§12" in section_ids

    def test_citation_confidence(self, verifier, sample_results):
        """Test confidence scoring for citations"""
        answer = "According to §5.2: Die Kündigungsfrist beträgt 3 Monate."

        citations = verifier.extract_citations(answer, sample_results)

        # Find §5.2 citation
        citation_52 = next(c for c in citations if "§5.2" in c.section_id)

        # Should have high confidence (content matches)
        assert citation_52.confidence > 0.7

    def test_hallucinated_citation(self, verifier, sample_results):
        """Test detection of hallucinated citations"""
        answer = "According to §99.9, something completely made up."

        citations = verifier.extract_citations(answer, sample_results)

        # Should still extract the citation
        hallucinated = next((c for c in citations if "§99" in c.section_id), None)

        if hallucinated:
            # Should have very low confidence
            assert hallucinated.confidence < 0.5

    def test_verify_supported_answer(self, verifier, sample_results):
        """Test verification of well-supported answer"""
        answer = "According to §5.2: Die Kündigungsfrist beträgt 3 Monate."

        result = verifier.verify_answer(answer, sample_results)

        assert result.confidence > 0.7
        assert len(result.unsupported_statements) == 0

    def test_detect_unsupported_claims(self, verifier, sample_results):
        """Test detection of unsupported claims"""
        answer = """
        According to §5.2: Die Kündigungsfrist beträgt 3 Monate.
        The contract must be notarized.
        Both parties must sign in person.
        """

        result = verifier.verify_answer(answer, sample_results)

        # Should detect unsupported claims
        assert len(result.unsupported_statements) > 0

    def test_extract_citing_sentences(self, verifier):
        """Test extraction of sentences with citations"""
        text = "Introduction. According to §5, xyz applies. Other text. As per §12, abc."

        sentences_5 = verifier._extract_citing_sentences(text, "§5")
        sentences_12 = verifier._extract_citing_sentences(text, "§12")

        assert len(sentences_5) >= 1
        assert len(sentences_12) >= 1
        assert "§5" in sentences_5[0]
        assert "§12" in sentences_12[0]

    def test_text_overlap_calculation(self, verifier):
        """Test text overlap ratio calculation"""
        text1 = "Die Kündigungsfrist beträgt drei Monate"
        text2 = "Die Kündigungsfrist beträgt 3 Monate zum Quartalsende"

        overlap = verifier._text_overlap(text1, text2)

        # Should have significant overlap
        assert overlap > 0.4

    def test_no_overlap(self, verifier):
        """Test text with no overlap"""
        text1 = "Completely different text"
        text2 = "Völlig anderer Inhalt"

        overlap = verifier._text_overlap(text1, text2)

        # Should have minimal overlap
        assert overlap < 0.2

    def test_verify_with_gemini_verification(self, verifier, sample_results):
        """Test combined verification with Gemini check"""
        answer = "According to §5.2: Die Kündigungsfrist beträgt 3 Monate."

        gemini_verification = {
            "is_supported": True,
            "verification_details": "✓ All statements supported",
        }

        result = verifier.verify_answer(
            answer, sample_results, gemini_verification=gemini_verification
        )

        assert result.is_supported is True
        assert result.confidence > 0.8

    def test_verify_with_gemini_rejection(self, verifier, sample_results):
        """Test when Gemini verification fails"""
        answer = "According to §5.2: Something incorrect."

        gemini_verification = {
            "is_supported": False,
            "verification_details": "- Unsupported claim detected",
        }

        result = verifier.verify_answer(
            answer, sample_results, gemini_verification=gemini_verification
        )

        assert result.is_supported is False

    def test_multiple_citations_same_section(self, verifier, sample_results):
        """Test handling multiple citations to same section"""
        answer = "§5.2 states X. Also, according to §5.2, Y applies."

        citations = verifier.extract_citations(answer, sample_results)

        # Should handle multiple references
        section_52_refs = [c for c in citations if "§5.2" in c.section_id]
        assert len(section_52_refs) >= 1
