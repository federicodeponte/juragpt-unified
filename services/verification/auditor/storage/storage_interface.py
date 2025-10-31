"""
ABOUTME: Storage interface for verification results and fingerprints
ABOUTME: Provides abstraction over SQLAlchemy for easy testing and swapping
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session, sessionmaker

from auditor.storage.database import (
    VerificationLog,
    SourceFingerprint,
    EmbeddingCache,
    init_database,
)


class StorageInterface:
    """
    Interface for storing and retrieving verification data.

    Provides methods for:
    - Storing verification results
    - Querying verification history
    - Managing source fingerprints
    - Caching embeddings
    """

    def __init__(self, database_url: str = "sqlite:///auditor.db"):
        """
        Initialize storage interface.

        Args:
            database_url: SQLAlchemy database URL
        """
        self.database_url = database_url
        self.SessionLocal = init_database(database_url)

    def _get_session(self) -> Session:
        """Get database session"""
        return self.SessionLocal()

    def store_verification(self, result: Dict[str, Any]) -> str:
        """
        Store verification result.

        Args:
            result: Verification result dict from VerificationService

        Returns:
            verification_id
        """
        session = self._get_session()

        try:
            log = VerificationLog(
                verification_id=result["verification_id"],
                created_at=datetime.fromisoformat(result["timestamp"]),
                answer_text=result["answer"]["text"],
                answer_hash=result.get("answer_hash", ""),
                answer_sentences=result["answer"]["total_sentences"],
                has_citations=result["answer"]["has_citations"],
                citations=result["answer"]["citations"],
                source_count=result["sources"]["count"],
                source_fingerprints=result["sources"]["fingerprints"],
                verified_sentences=result["verification"]["verified_sentences"],
                verification_rate=result["verification"]["verification_rate"],
                confidence_score=result["confidence"]["score"],
                trust_label=result["confidence"]["trust_label"],
                semantic_similarity=result["confidence"]["components"].get("semantic_similarity"),
                retrieval_quality=result["confidence"]["components"].get("retrieval_quality"),
                citation_presence=result["confidence"]["components"].get("citation_presence"),
                coverage=result["confidence"]["components"].get("coverage"),
                retry_attempts=result.get("retry_info", {}).get("attempts", 0),
                extra_metadata=result.get("metadata"),
                duration_ms=result.get("duration_ms"),
            )

            session.add(log)
            session.commit()

            return log.verification_id

        finally:
            session.close()

    def get_verification(self, verification_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve verification result by ID.

        Args:
            verification_id: Verification ID

        Returns:
            Verification dict or None
        """
        session = self._get_session()

        try:
            log = session.query(VerificationLog).filter(
                VerificationLog.verification_id == verification_id
            ).first()

            if not log:
                return None

            return self._log_to_dict(log)

        finally:
            session.close()

    def get_verifications(
        self,
        limit: int = 100,
        offset: int = 0,
        min_confidence: Optional[float] = None,
        trust_label: Optional[str] = None,
        valid_only: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Query verification logs.

        Args:
            limit: Maximum results
            offset: Skip offset
            min_confidence: Minimum confidence score
            trust_label: Filter by trust label
            valid_only: Only return valid (not invalidated) verifications

        Returns:
            List of verification dicts
        """
        session = self._get_session()

        try:
            query = session.query(VerificationLog)

            if min_confidence is not None:
                query = query.filter(VerificationLog.confidence_score >= min_confidence)

            if trust_label:
                query = query.filter(VerificationLog.trust_label == trust_label)

            if valid_only:
                query = query.filter(VerificationLog.is_valid == True)

            logs = query.order_by(VerificationLog.created_at.desc()).limit(limit).offset(offset).all()

            return [self._log_to_dict(log) for log in logs]

        finally:
            session.close()

    def invalidate_verification(self, verification_id: str) -> bool:
        """
        Invalidate a verification (when source changes).

        Args:
            verification_id: Verification ID

        Returns:
            True if invalidated, False if not found
        """
        session = self._get_session()

        try:
            log = session.query(VerificationLog).filter(
                VerificationLog.verification_id == verification_id
            ).first()

            if not log:
                return False

            log.is_valid = False
            log.invalidated_at = datetime.now()
            session.commit()

            return True

        finally:
            session.close()

    def store_fingerprint(
        self,
        source_id: str,
        source_hash: str,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> int:
        """
        Store source fingerprint.

        Args:
            source_id: Source identifier
            source_hash: SHA-256 hash
            text: Source text
            metadata: Optional metadata

        Returns:
            Fingerprint database ID
        """
        session = self._get_session()

        try:
            fingerprint = SourceFingerprint(
                source_id=source_id,
                source_hash=source_hash,
                text=text,
                text_length=len(text),
                extra_metadata=metadata,
            )

            session.add(fingerprint)
            session.commit()

            return fingerprint.id

        finally:
            session.close()

    def get_fingerprint_by_hash(self, source_hash: str) -> Optional[Dict[str, Any]]:
        """Get fingerprint by hash"""
        session = self._get_session()

        try:
            fp = session.query(SourceFingerprint).filter(
                SourceFingerprint.source_hash == source_hash
            ).first()

            if not fp:
                return None

            return self._fingerprint_to_dict(fp)

        finally:
            session.close()

    def get_statistics(self) -> Dict[str, Any]:
        """Get storage statistics"""
        session = self._get_session()

        try:
            total_verifications = session.query(VerificationLog).count()
            valid_verifications = session.query(VerificationLog).filter(
                VerificationLog.is_valid == True
            ).count()

            verified_count = session.query(VerificationLog).filter(
                VerificationLog.trust_label == "✅ Verified"
            ).count()

            review_count = session.query(VerificationLog).filter(
                VerificationLog.trust_label == "⚠️ Review"
            ).count()

            rejected_count = session.query(VerificationLog).filter(
                VerificationLog.trust_label == "🚫 Rejected"
            ).count()

            avg_confidence = session.query(VerificationLog).filter(
                VerificationLog.is_valid == True
            ).with_entities(VerificationLog.confidence_score).all()

            avg_conf_score = sum(c[0] for c in avg_confidence) / len(avg_confidence) if avg_confidence else 0.0

            return {
                "total_verifications": total_verifications,
                "valid_verifications": valid_verifications,
                "invalid_verifications": total_verifications - valid_verifications,
                "by_label": {
                    "verified": verified_count,
                    "review": review_count,
                    "rejected": rejected_count,
                },
                "average_confidence": avg_conf_score,
                "total_fingerprints": session.query(SourceFingerprint).count(),
                "total_embeddings_cached": session.query(EmbeddingCache).count(),
            }

        finally:
            session.close()

    def _log_to_dict(self, log: VerificationLog) -> Dict[str, Any]:
        """Convert VerificationLog to dict"""
        return {
            "verification_id": log.verification_id,
            "created_at": log.created_at.isoformat(),
            "answer": {
                "text": log.answer_text,
                "sentences": log.answer_sentences,
                "has_citations": log.has_citations,
                "citations": log.citations,
            },
            "sources": {
                "count": log.source_count,
                "fingerprints": log.source_fingerprints,
            },
            "verification": {
                "verified_sentences": log.verified_sentences,
                "verification_rate": log.verification_rate,
            },
            "confidence": {
                "score": log.confidence_score,
                "trust_label": log.trust_label,
                "components": {
                    "semantic_similarity": log.semantic_similarity,
                    "retrieval_quality": log.retrieval_quality,
                    "citation_presence": log.citation_presence,
                    "coverage": log.coverage,
                },
            },
            "is_valid": log.is_valid,
            "invalidated_at": log.invalidated_at.isoformat() if log.invalidated_at else None,
            "duration_ms": log.duration_ms,
            "metadata": log.extra_metadata,
        }

    def _fingerprint_to_dict(self, fp: SourceFingerprint) -> Dict[str, Any]:
        """Convert SourceFingerprint to dict"""
        return {
            "id": fp.id,
            "source_id": fp.source_id,
            "source_hash": fp.source_hash,
            "text": fp.text,
            "text_length": fp.text_length,
            "version": fp.version,
            "created_at": fp.created_at.isoformat(),
            "metadata": fp.extra_metadata,
        }


def main() -> None:
    """Demo usage of storage interface"""
    print("💾 Storage Interface Demo\n")

    storage = StorageInterface("sqlite:///demo_storage.db")

    # Mock verification result
    mock_result = {
        "verification_id": "test_001",
        "timestamp": datetime.now().isoformat(),
        "answer": {
            "text": "Test answer",
            "total_sentences": 2,
            "has_citations": True,
            "citations": ["§ 823 BGB"],
        },
        "sources": {
            "count": 1,
            "fingerprints": ["abc123"],
        },
        "verification": {
            "verified_sentences": 2,
            "total_sentences": 2,
            "verification_rate": 1.0,
        },
        "confidence": {
            "score": 0.92,
            "trust_label": "✅ Verified",
            "components": {
                "semantic_similarity": 0.95,
                "retrieval_quality": 0.88,
                "citation_presence": 0.90,
                "coverage": 1.0,
            },
        },
        "duration_ms": 145.3,
    }

    # Store
    print("Storing verification...")
    vid = storage.store_verification(mock_result)
    print(f"✓ Stored: {vid}")

    # Retrieve
    print("\nRetrieving verification...")
    retrieved = storage.get_verification(vid)
    print(f"✓ Retrieved: {retrieved['confidence']['trust_label']}")
    print(f"  Confidence: {retrieved['confidence']['score']}")

    # Query
    print("\nQuerying verifications (confidence >= 0.90)...")
    results = storage.get_verifications(min_confidence=0.90, limit=10)
    print(f"✓ Found {len(results)} results")

    # Statistics
    print("\n" + "=" * 60)
    stats = storage.get_statistics()
    print("\n📊 Storage Statistics:")
    for key, value in stats.items():
        if isinstance(value, dict):
            print(f"  {key}:")
            for k, v in value.items():
                print(f"    {k}: {v}")
        else:
            print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
