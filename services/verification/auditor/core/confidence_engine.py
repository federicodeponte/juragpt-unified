"""
ABOUTME: Multi-factor confidence scoring for verification results
ABOUTME: Combines semantic similarity, retrieval scores, and other signals into unified confidence metric
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import statistics


@dataclass
class VerificationSignals:
    """Container for verification signals used in confidence calculation"""

    # Semantic similarity scores
    sentence_scores: List[float]  # Score per sentence
    retrieval_scores: List[float]  # Retrieval scores from sources

    # Metadata signals
    has_citations: bool = False
    citation_count: int = 0
    source_count: int = 0

    # Optional additional signals
    token_overlap: Optional[float] = None
    source_diversity: Optional[float] = None


class ConfidenceEngine:
    """
    Calculates confidence scores using multiple verification signals.

    Combines:
    - Semantic similarity (primary)
    - Retrieval quality
    - Citation presence
    - Source diversity
    """

    def __init__(
        self,
        sentence_threshold: float = 0.75,
        overall_threshold: float = 0.80,
        weights: Optional[Dict[str, float]] = None,
    ):
        """
        Initialize confidence engine.

        Args:
            sentence_threshold: Minimum similarity for sentence verification
            overall_threshold: Minimum confidence for overall verification
            weights: Custom weights for different signals (default: balanced)
        """
        self.sentence_threshold = sentence_threshold
        self.overall_threshold = overall_threshold

        # Default weights (must sum to 1.0)
        self.weights = weights or {
            "semantic_similarity": 0.60,  # Primary signal
            "retrieval_quality": 0.25,  # Source relevance
            "citation_presence": 0.10,  # Has legal citations
            "coverage": 0.05,  # Sentence coverage ratio
        }

        # Validate weights
        total = sum(self.weights.values())
        if abs(total - 1.0) > 0.01:
            raise ValueError(f"Weights must sum to 1.0, got {total}")

    def calculate_semantic_score(self, sentence_scores: List[float]) -> float:
        """
        Calculate semantic similarity component.

        Uses average of all sentence scores with penalty for low scores.

        Args:
            sentence_scores: List of similarity scores (0-1)

        Returns:
            Weighted semantic score
        """
        if not sentence_scores:
            return 0.0

        # Base score: average
        avg_score = statistics.mean(sentence_scores)

        # Penalty for variance (inconsistent verification)
        if len(sentence_scores) > 1:
            variance = statistics.variance(sentence_scores)
            variance_penalty = min(0.15, variance * 0.5)  # Max 15% penalty
            avg_score -= variance_penalty

        # Penalty for low scores
        low_score_count = sum(1 for s in sentence_scores if s < self.sentence_threshold)
        low_score_ratio = low_score_count / len(sentence_scores)
        low_score_penalty = low_score_ratio * 0.20  # Up to 20% penalty

        final_score = max(0.0, avg_score - low_score_penalty)

        return final_score

    def calculate_retrieval_score(self, retrieval_scores: List[float]) -> float:
        """
        Calculate retrieval quality component.

        High retrieval scores indicate sources are relevant.

        Args:
            retrieval_scores: Scores from retrieval system

        Returns:
            Retrieval quality score
        """
        if not retrieval_scores:
            return 0.5  # Neutral if no retrieval scores

        # Use top-3 average if available, else all
        top_scores = sorted(retrieval_scores, reverse=True)[:3]
        return statistics.mean(top_scores)

    def calculate_citation_score(self, has_citations: bool, citation_count: int) -> float:
        """
        Calculate citation presence component.

        Answers with legal citations are more likely to be grounded.

        Args:
            has_citations: Whether answer contains citations
            citation_count: Number of citations found

        Returns:
            Citation score (0-1)
        """
        if not has_citations:
            return 0.3  # Neutral-low score

        # More citations = higher confidence (with diminishing returns)
        if citation_count == 1:
            return 0.7
        elif citation_count == 2:
            return 0.85
        else:
            return min(1.0, 0.85 + (citation_count - 2) * 0.05)

    def calculate_coverage_score(self, verified_count: int, total_count: int) -> float:
        """
        Calculate sentence coverage component.

        What percentage of sentences are verified?

        Args:
            verified_count: Number of verified sentences
            total_count: Total sentences

        Returns:
            Coverage ratio (0-1)
        """
        if total_count == 0:
            return 0.0

        return verified_count / total_count

    def calculate_confidence(self, signals: VerificationSignals) -> Dict[str, Any]:
        """
        Calculate overall confidence score from all signals.

        Args:
            signals: Verification signals

        Returns:
            Dict with:
                - confidence: overall score (0-1)
                - components: breakdown by component
                - verified: whether confidence exceeds threshold
        """
        # Calculate individual components
        semantic_score = self.calculate_semantic_score(signals.sentence_scores)
        retrieval_score = self.calculate_retrieval_score(signals.retrieval_scores)
        citation_score = self.calculate_citation_score(
            signals.has_citations, signals.citation_count
        )

        # Coverage (how many sentences verified)
        verified_count = sum(1 for s in signals.sentence_scores if s >= self.sentence_threshold)
        total_count = len(signals.sentence_scores)
        coverage_score = self.calculate_coverage_score(verified_count, total_count)

        # Weighted combination
        confidence = (
            semantic_score * self.weights["semantic_similarity"]
            + retrieval_score * self.weights["retrieval_quality"]
            + citation_score * self.weights["citation_presence"]
            + coverage_score * self.weights["coverage"]
        )

        # Ensure in [0, 1]
        confidence = max(0.0, min(1.0, confidence))

        return {
            "confidence": confidence,
            "verified": confidence >= self.overall_threshold,
            "components": {
                "semantic_similarity": semantic_score,
                "retrieval_quality": retrieval_score,
                "citation_presence": citation_score,
                "coverage": coverage_score,
            },
            "thresholds": {
                "sentence": self.sentence_threshold,
                "overall": self.overall_threshold,
            },
            "statistics": {
                "verified_sentences": verified_count,
                "total_sentences": total_count,
                "verification_rate": coverage_score,
            },
        }

    def get_trust_label(self, confidence: float) -> str:
        """
        Map confidence score to trust label.

        Args:
            confidence: Confidence score (0-1)

        Returns:
            Trust label: "✅ Verified", "⚠️ Review", or "🚫 Rejected"
        """
        if confidence >= self.overall_threshold:
            return "✅ Verified"
        elif confidence >= 0.60:  # Review threshold
            return "⚠️ Review"
        else:
            return "🚫 Rejected"

    def should_retry(self, confidence: float, retry_threshold: float = 0.60) -> bool:
        """
        Determine if verification should be retried with better context.

        Args:
            confidence: Current confidence score
            retry_threshold: Threshold below which to retry

        Returns:
            True if should retry
        """
        return confidence < retry_threshold

    def explain_confidence(self, result: Dict[str, Any]) -> str:
        """
        Generate human-readable explanation of confidence score.

        Args:
            result: Result from calculate_confidence()

        Returns:
            Explanation string
        """
        conf = result["confidence"]
        comps = result["components"]
        stats = result["statistics"]

        explanation = f"Confidence: {conf:.2f} ({self.get_trust_label(conf)})\n\n"

        explanation += "Component Breakdown:\n"
        explanation += f"  • Semantic Similarity: {comps['semantic_similarity']:.2f} "
        explanation += f"(weight: {self.weights['semantic_similarity']:.0%})\n"
        explanation += f"  • Retrieval Quality: {comps['retrieval_quality']:.2f} "
        explanation += f"(weight: {self.weights['retrieval_quality']:.0%})\n"
        explanation += f"  • Citation Presence: {comps['citation_presence']:.2f} "
        explanation += f"(weight: {self.weights['citation_presence']:.0%})\n"
        explanation += f"  • Coverage: {comps['coverage']:.2f} "
        explanation += f"(weight: {self.weights['coverage']:.0%})\n\n"

        explanation += "Statistics:\n"
        explanation += f"  • Verified Sentences: {stats['verified_sentences']}/{stats['total_sentences']}\n"
        explanation += f"  • Verification Rate: {stats['verification_rate']:.1%}\n"

        if self.should_retry(conf):
            explanation += "\n⚠️ Recommendation: Retry with improved context"

        return explanation


def main() -> None:
    """Demo usage of confidence engine"""
    print("⚖️ Confidence Engine Demo\n")

    engine = ConfidenceEngine(
        sentence_threshold=0.75,
        overall_threshold=0.80,
    )

    # Test Case 1: High confidence (well-supported)
    print("Test Case 1: Well-Supported Answer")
    print("=" * 60)

    signals1 = VerificationSignals(
        sentence_scores=[0.92, 0.88, 0.85],  # All high
        retrieval_scores=[0.95, 0.89, 0.82],
        has_citations=True,
        citation_count=2,
        source_count=3,
    )

    result1 = engine.calculate_confidence(signals1)
    print(engine.explain_confidence(result1))

    # Test Case 2: Medium confidence (partial support)
    print("\n\nTest Case 2: Partially Supported Answer")
    print("=" * 60)

    signals2 = VerificationSignals(
        sentence_scores=[0.82, 0.68, 0.75],  # Mixed
        retrieval_scores=[0.78, 0.65],
        has_citations=True,
        citation_count=1,
        source_count=2,
    )

    result2 = engine.calculate_confidence(signals2)
    print(engine.explain_confidence(result2))

    # Test Case 3: Low confidence (hallucination)
    print("\n\nTest Case 3: Hallucinated Answer")
    print("=" * 60)

    signals3 = VerificationSignals(
        sentence_scores=[0.55, 0.48, 0.62],  # All low
        retrieval_scores=[0.60],
        has_citations=False,
        citation_count=0,
        source_count=1,
    )

    result3 = engine.calculate_confidence(signals3)
    print(engine.explain_confidence(result3))


if __name__ == "__main__":
    main()
