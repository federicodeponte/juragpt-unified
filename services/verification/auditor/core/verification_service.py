"""
ABOUTME: Main verification service orchestrator
ABOUTME: Coordinates all verification components and implements auto-retry logic
"""

import uuid
from typing import List, Dict, Any, Optional
from datetime import datetime

from auditor.core.sentence_processor import SentenceProcessor
from auditor.core.semantic_matcher import SemanticMatcher
from auditor.core.confidence_engine import ConfidenceEngine, VerificationSignals
from auditor.core.fingerprint_tracker import FingerprintTracker
from auditor.config.settings import Settings


class VerificationService:
    """
    Main verification service that orchestrates all components.

    Workflow:
    1. Split answer into sentences (SentenceProcessor)
    2. Match each sentence against sources (SemanticMatcher)
    3. Calculate confidence score (ConfidenceEngine)
    4. Create fingerprints for audit (FingerprintTracker)
    5. Auto-retry if confidence too low
    """

    def __init__(
        self,
        settings: Optional[Settings] = None,
        sentence_processor: Optional[SentenceProcessor] = None,
        semantic_matcher: Optional[SemanticMatcher] = None,
        confidence_engine: Optional[ConfidenceEngine] = None,
        fingerprint_tracker: Optional[FingerprintTracker] = None,
    ):
        """
        Initialize verification service.

        Args:
            settings: Configuration settings
            sentence_processor: Custom sentence processor (optional)
            semantic_matcher: Custom semantic matcher (optional)
            confidence_engine: Custom confidence engine (optional)
            fingerprint_tracker: Custom fingerprint tracker (optional)
        """
        self.settings = settings or Settings()

        # Initialize components
        self.sentence_processor = sentence_processor or SentenceProcessor(
            model_name=self.settings.spacy_model
        )

        self.semantic_matcher = semantic_matcher or SemanticMatcher(
            model_name=self.settings.embedding_model,
            device="cpu",
            cache_enabled=self.settings.enable_embedding_cache,
            cache_size=self.settings.max_cache_size,
        )

        self.confidence_engine = confidence_engine or ConfidenceEngine(
            sentence_threshold=self.settings.sentence_threshold,
            overall_threshold=self.settings.overall_threshold,
        )

        self.fingerprint_tracker = fingerprint_tracker or FingerprintTracker(
            auto_invalidate=True
        )

        # Retry configuration
        self.max_retries = self.settings.max_retries
        self.retry_threshold = self.settings.auto_retry_threshold

    def verify(
        self,
        answer: str,
        sources: List[Dict[str, str]],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Verify an answer against source snippets.

        Args:
            answer: Generated answer text
            sources: List of dicts with 'text' and optional 'source_id', 'score'
            metadata: Optional metadata to include

        Returns:
            Verification result dict
        """
        verification_id = str(uuid.uuid4())
        start_time = datetime.now()

        # Step 1: Process answer into sentences
        processed = self.sentence_processor.process_answer(answer)
        sentences = [s["text"] for s in processed["sentences"]]

        if not sentences:
            return self._create_empty_result(verification_id, answer, "no_sentences")

        if not sources:
            return self._create_empty_result(verification_id, answer, "no_sources")

        # Step 2: Extract source texts and scores
        source_texts = [src["text"] for src in sources]
        retrieval_scores = [src.get("score", 0.5) for src in sources]

        # Step 3: Verify each sentence
        verification_result = self.semantic_matcher.verify_answer(
            sentences=sentences,
            sources=source_texts,
            sentence_threshold=self.settings.sentence_threshold,
        )

        # Step 4: Collect signals for confidence calculation
        sentence_scores = [s["max_score"] for s in verification_result["sentences"]]

        signals = VerificationSignals(
            sentence_scores=sentence_scores,
            retrieval_scores=retrieval_scores,
            has_citations=processed["has_citations"],
            citation_count=len(processed["citations"]),
            source_count=len(sources),
        )

        # Step 5: Calculate confidence
        confidence_result = self.confidence_engine.calculate_confidence(signals)

        # Step 6: Create fingerprints
        fingerprints = self.fingerprint_tracker.fingerprint_sources(sources)

        # Step 7: Record verification
        self.fingerprint_tracker.record_verification(
            verification_id=verification_id,
            answer_text=answer,
            source_fingerprints=fingerprints,
            confidence=confidence_result["confidence"],
            trust_label=confidence_result["verified"],
        )

        # Calculate duration
        duration_ms = (datetime.now() - start_time).total_seconds() * 1000

        # Assemble result
        result = {
            "verification_id": verification_id,
            "timestamp": start_time.isoformat(),
            "duration_ms": duration_ms,
            "answer": {
                "text": answer,
                "total_sentences": len(sentences),
                "has_citations": processed["has_citations"],
                "citations": processed["citations"],
            },
            "sources": {
                "count": len(sources),
                "fingerprints": [
                    self.fingerprint_tracker.truncate_hash(fp.hash) for fp in fingerprints
                ],
            },
            "verification": {
                "verified_sentences": verification_result["verified_count"],
                "total_sentences": verification_result["total_count"],
                "verification_rate": verification_result["verification_rate"],
                "sentences": verification_result["sentences"],
            },
            "confidence": {
                "score": confidence_result["confidence"],
                "verified": confidence_result["verified"],
                "trust_label": self.confidence_engine.get_trust_label(
                    confidence_result["confidence"]
                ),
                "components": confidence_result["components"],
            },
            "metadata": metadata or {},
        }

        return result

    def verify_with_retry(
        self,
        answer: str,
        sources: List[Dict[str, str]],
        metadata: Optional[Dict[str, Any]] = None,
        retry_callback: Optional[callable] = None,
    ) -> Dict[str, Any]:
        """
        Verify with auto-retry if confidence is too low.

        Args:
            answer: Answer text
            sources: Source snippets
            metadata: Optional metadata
            retry_callback: Optional function to get better sources on retry
                           Should accept (answer, confidence) and return new sources

        Returns:
            Verification result (potentially after retries)
        """
        attempt = 0
        result = None

        while attempt <= self.max_retries:
            # Perform verification
            result = self.verify(answer, sources, metadata)

            confidence = result["confidence"]["score"]

            # Check if retry needed
            if not self.settings.auto_retry_enabled:
                break

            if confidence >= self.retry_threshold:
                break  # Confidence sufficient

            if attempt >= self.max_retries:
                break  # Max retries reached

            # Retry with better sources
            if retry_callback:
                print(f"⚠️  Retrying (attempt {attempt + 1}): confidence {confidence:.2f} < {self.retry_threshold}")
                sources = retry_callback(answer, confidence)
            else:
                break  # No callback, can't improve

            attempt += 1

        # Add retry info to result
        result["retry_info"] = {
            "enabled": self.settings.auto_retry_enabled,
            "attempts": attempt,
            "max_retries": self.max_retries,
            "threshold": self.retry_threshold,
        }

        return result

    def batch_verify(
        self, items: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Verify multiple answers in batch.

        Args:
            items: List of dicts with 'answer' and 'sources'

        Returns:
            List of verification results
        """
        results = []

        for item in items:
            result = self.verify(
                answer=item["answer"],
                sources=item["sources"],
                metadata=item.get("metadata"),
            )
            results.append(result)

        return results

    def _create_empty_result(
        self, verification_id: str, answer: str, reason: str
    ) -> Dict[str, Any]:
        """Create empty result for edge cases"""
        return {
            "verification_id": verification_id,
            "timestamp": datetime.now().isoformat(),
            "answer": {"text": answer},
            "confidence": {
                "score": 0.0,
                "verified": False,
                "trust_label": "🚫 Rejected",
            },
            "error": reason,
        }

    def get_verification_history(self, source_id: str) -> List[Dict[str, Any]]:
        """Get all verifications using a specific source"""
        return self.fingerprint_tracker.get_audit_trail(source_id)

    def invalidate_source(self, source_id: str, new_text: str) -> Dict[str, Any]:
        """Update source and invalidate affected verifications"""
        return self.fingerprint_tracker.update_source(source_id, new_text)

    def get_statistics(self) -> Dict[str, Any]:
        """Get service statistics"""
        return {
            "fingerprint_tracker": self.fingerprint_tracker.get_statistics(),
            "semantic_matcher": self.semantic_matcher.get_cache_stats(),
            "configuration": {
                "sentence_threshold": self.settings.sentence_threshold,
                "overall_threshold": self.settings.overall_threshold,
                "auto_retry_enabled": self.settings.auto_retry_enabled,
                "max_retries": self.settings.max_retries,
            },
        }


def main() -> None:
    """Demo usage of verification service"""
    print("🔍 Verification Service Demo\n")

    # Initialize service
    service = VerificationService()

    # Test data
    answer = """
    Nach § 823 Abs. 1 BGB haftet, wer vorsätzlich oder fahrlässig das Leben,
    den Körper, die Gesundheit, die Freiheit, das Eigentum oder ein sonstiges
    Recht eines anderen widerrechtlich verletzt. Der Schädiger ist zum Ersatz
    des daraus entstehenden Schadens verpflichtet.
    """

    sources = [
        {
            "source_id": "bgb_823_1",
            "text": "Wer vorsätzlich oder fahrlässig das Leben, den Körper, die Gesundheit, die Freiheit, das Eigentum oder ein sonstiges Recht eines anderen widerrechtlich verletzt, ist dem anderen zum Ersatz des daraus entstehenden Schadens verpflichtet.",
            "score": 0.95,
        },
        {
            "source_id": "bgb_276",
            "text": "Der Schuldner hat Vorsatz und Fahrlässigkeit zu vertreten, sofern nicht ein anderes bestimmt ist.",
            "score": 0.78,
        },
    ]

    print("Answer:")
    print(answer.strip())
    print("\n" + "=" * 60 + "\n")

    # Verify
    result = service.verify(answer, sources)

    print(f"Verification ID: {result['verification_id']}")
    print(f"Duration: {result['duration_ms']:.1f}ms\n")

    print("Answer Analysis:")
    print(f"  Sentences: {result['answer']['total_sentences']}")
    print(f"  Citations: {result['answer']['citations']}\n")

    print("Verification Results:")
    print(f"  Verified: {result['verification']['verified_sentences']}/{result['verification']['total_sentences']}")
    print(f"  Rate: {result['verification']['verification_rate']:.1%}\n")

    print("Confidence:")
    print(f"  Score: {result['confidence']['score']:.2f}")
    print(f"  Label: {result['confidence']['trust_label']}")
    print(f"  Components:")
    for comp, score in result["confidence"]["components"].items():
        print(f"    - {comp}: {score:.2f}")

    print("\n" + "=" * 60)
    stats = service.get_statistics()
    print("\n📊 Service Statistics:")
    print(f"  Fingerprints: {stats['fingerprint_tracker']['total_fingerprints']}")
    print(f"  Verifications: {stats['fingerprint_tracker']['total_verifications']}")
    print(f"  Cache Size: {stats['semantic_matcher']['cache_size']}")


if __name__ == "__main__":
    main()
