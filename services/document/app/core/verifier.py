"""
ABOUTME: Verification layer for citation checking and hallucination detection
ABOUTME: Validates that all claims in responses are supported by source documents
"""

import re
import uuid
from typing import Dict, List, Optional

from app.core.document_parser import DocumentParser
from app.db.models import Citation, RetrievalResult, VerificationResult
from app.utils.logging import logger


class Verifier:
    """
    Verify that generated answers are properly cited and supported
    Detects hallucinations and unsupported claims
    """

    def __init__(self):
        self.parser = DocumentParser()

    def extract_citations(
        self, answer: str, retrieval_results: List[RetrievalResult]
    ) -> List[Citation]:
        """
        Extract citations from answer and match to source chunks

        Args:
            answer: Generated answer text
            retrieval_results: Retrieved chunks that were used

        Returns:
            List of Citation objects with confidence scores
        """
        # Extract section IDs mentioned in answer
        cited_section_ids = self.parser.extract_section_numbers(answer)

        citations = []

        for section_id in cited_section_ids:
            # Find matching retrieval result
            matching_result = self._find_matching_chunk(section_id, retrieval_results)

            if matching_result:
                # Calculate confidence based on similarity and text matching
                confidence = self._calculate_citation_confidence(
                    section_id, answer, matching_result
                )

                citation = Citation(
                    section_id=section_id,
                    content=matching_result.content[:500],  # Truncate for response
                    confidence=confidence,
                    chunk_id=matching_result.chunk_id,
                )
                citations.append(citation)
            else:
                # Citation mentioned but not in retrieved chunks (potential hallucination)
                logger.warning(f"Citation {section_id} not found in retrieved chunks")
                citations.append(
                    Citation(
                        section_id=section_id,
                        content="[Citation not found in retrieved sections]",
                        confidence=0.0,
                        chunk_id=uuid.uuid4(),  # Placeholder
                    )
                )

        return citations

    def verify_answer(
        self,
        answer: str,
        retrieval_results: List[RetrievalResult],
        gemini_verification: Optional[Dict] = None,
    ) -> VerificationResult:
        """
        Comprehensive verification of answer quality

        Args:
            answer: Generated answer
            retrieval_results: Source chunks
            gemini_verification: Optional verification from Gemini

        Returns:
            VerificationResult with support status and details
        """
        # 1. Extract citations from answer
        citations = self.extract_citations(answer, retrieval_results)

        # 2. Check for unsupported statements
        unsupported = self._detect_unsupported_claims(answer, retrieval_results, citations)

        # 3. Calculate overall confidence
        if citations:
            avg_confidence = sum(c.confidence for c in citations) / len(citations)
        else:
            avg_confidence = 0.5  # No citations is concerning but not always wrong

        # Penalty for unsupported claims
        if unsupported:
            avg_confidence *= 0.6  # 40% penalty

        # 4. Combine with Gemini's self-verification if available
        is_supported = len(unsupported) == 0

        if gemini_verification:
            is_supported = is_supported and gemini_verification.get("is_supported", True)

        citation_matches = [c.section_id for c in citations if c.confidence > 0.7]

        result = VerificationResult(
            is_supported=is_supported,
            citation_matches=citation_matches,
            unsupported_statements=unsupported,
            confidence=avg_confidence,
        )

        logger.info(
            f"Verification: {'PASS' if is_supported else 'FAIL'}",
            extra={
                "citations_found": len(citations),
                "high_confidence_citations": len(citation_matches),
                "unsupported_count": len(unsupported),
                "overall_confidence": avg_confidence,
            },
        )

        return result

    def _find_matching_chunk(
        self, section_id: str, retrieval_results: List[RetrievalResult]
    ) -> RetrievalResult | None:
        """Find retrieval result matching section ID"""
        for result in retrieval_results:
            if section_id.lower() in result.section_id.lower():
                return result

            # Check if section ID appears in content
            if section_id.lower() in result.content.lower():
                return result

        return None

    def _calculate_citation_confidence(
        self, section_id: str, answer: str, result: RetrievalResult
    ) -> float:
        """
        Calculate confidence score for a citation

        Based on:
        - Vector similarity of chunk
        - Whether content matches quoted text
        - Proximity of citation to statement
        """
        confidence = result.similarity  # Start with vector similarity

        # Extract sentences containing this citation
        sentences = self._extract_citing_sentences(answer, section_id)

        if sentences:
            # Check if any sentence content appears in chunk
            for sentence in sentences:
                # Remove the citation marker itself
                sentence_content = re.sub(r"§\s*\d+\.?\d*", "", sentence).strip()

                # Check overlap with chunk content
                if self._text_overlap(sentence_content, result.content) > 0.5:
                    confidence = min(confidence + 0.15, 1.0)  # Boost confidence

        return confidence

    def _extract_citing_sentences(self, text: str, section_id: str) -> List[str]:
        """Extract sentences that cite a specific section"""
        # Split into sentences
        sentences = re.split(r"[.!?]\s+", text)

        citing_sentences = []
        for sentence in sentences:
            if section_id.lower() in sentence.lower():
                citing_sentences.append(sentence)

        return citing_sentences

    def _text_overlap(self, text1: str, text2: str) -> float:
        """
        Calculate text overlap ratio (simple word-based)
        Returns value between 0 and 1
        """
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        if not words1 or not words2:
            return 0.0

        intersection = words1.intersection(words2)
        union = words1.union(words2)

        return len(intersection) / len(union)

    def _detect_unsupported_claims(
        self, answer: str, retrieval_results: List[RetrievalResult], citations: List[Citation]
    ) -> List[str]:
        """
        Detect statements that lack proper citation support

        Heuristics:
        - Statements without citations
        - Citations with low confidence (<0.5)
        - Definitive claims without quoted support
        """
        unsupported = []

        # Split answer into sentences
        sentences = re.split(r"[.!?]\s+", answer)

        # Collect all cited section IDs with high confidence
        supported_sections = set(c.section_id for c in citations if c.confidence > 0.5)

        for sentence in sentences:
            # Skip very short sentences
            if len(sentence.split()) < 5:
                continue

            # Check if sentence makes a claim (has definitive language)
            is_claim = any(
                keyword in sentence.lower()
                for keyword in [
                    "must",
                    "shall",
                    "muss",
                    "ist",
                    "hat",
                    "kann",
                    "darf",
                    "requires",
                    "states",
                    "provides",
                    "besagt",
                    "regelt",
                ]
            )

            if not is_claim:
                continue

            # Check if sentence has a citation
            has_citation = any(section in sentence for section in supported_sections)

            if not has_citation:
                # Flag as potentially unsupported
                unsupported.append(sentence.strip())

        return unsupported


# Global instance
verifier = Verifier()
