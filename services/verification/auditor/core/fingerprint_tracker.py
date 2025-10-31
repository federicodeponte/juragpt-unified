"""
ABOUTME: Citation fingerprinting for source change detection and audit trails
ABOUTME: Uses SHA-256 hashing to track source document versions and invalidate stale verifications
"""

import hashlib
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime
import json


@dataclass
class SourceFingerprint:
    """Fingerprint for a source snippet"""

    source_id: str
    text: str
    hash: str
    created_at: datetime
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "source_id": self.source_id,
            "text": self.text,
            "hash": self.hash,
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SourceFingerprint":
        """Create from dictionary"""
        data["created_at"] = datetime.fromisoformat(data["created_at"])
        return cls(**data)


@dataclass
class VerificationRecord:
    """Record of a verification with fingerprints"""

    verification_id: str
    answer_text: str
    answer_hash: str
    source_fingerprints: List[str]  # List of source hashes
    confidence: float
    trust_label: str
    created_at: datetime
    is_valid: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "verification_id": self.verification_id,
            "answer_text": self.answer_text,
            "answer_hash": self.answer_hash,
            "source_fingerprints": self.source_fingerprints,
            "confidence": self.confidence,
            "trust_label": self.trust_label,
            "created_at": self.created_at.isoformat(),
            "is_valid": self.is_valid,
        }


class FingerprintTracker:
    """
    Tracks fingerprints of sources and answers for change detection.

    Features:
    - SHA-256 hashing of source texts
    - Change detection when sources update
    - Automatic invalidation of affected verifications
    - Audit trail for all verifications
    """

    def __init__(
        self,
        algorithm: str = "sha256",
        truncate_length: int = 16,
        auto_invalidate: bool = True,
    ):
        """
        Initialize fingerprint tracker.

        Args:
            algorithm: Hash algorithm (default: sha256)
            truncate_length: Display length for hashes
            auto_invalidate: Auto-invalidate verifications on source change
        """
        self.algorithm = algorithm
        self.truncate_length = truncate_length
        self.auto_invalidate = auto_invalidate

        # In-memory stores (would be DB in production)
        self._fingerprints: Dict[str, SourceFingerprint] = {}
        self._verifications: Dict[str, VerificationRecord] = {}

        # Index: source_hash -> verification_ids
        self._source_to_verifications: Dict[str, Set[str]] = {}

    def compute_hash(self, text: str) -> str:
        """
        Compute SHA-256 hash of text.

        Args:
            text: Input text

        Returns:
            Hex digest hash string
        """
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def truncate_hash(self, hash: str) -> str:
        """Truncate hash for display"""
        return hash[: self.truncate_length]

    def create_fingerprint(
        self,
        source_id: str,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> SourceFingerprint:
        """
        Create fingerprint for a source.

        Args:
            source_id: Unique identifier for source
            text: Source text
            metadata: Optional metadata

        Returns:
            SourceFingerprint object
        """
        hash = self.compute_hash(text)

        fingerprint = SourceFingerprint(
            source_id=source_id,
            text=text,
            hash=hash,
            created_at=datetime.now(),
            metadata=metadata or {},
        )

        # Store fingerprint
        self._fingerprints[hash] = fingerprint

        return fingerprint

    def fingerprint_sources(
        self, sources: List[Dict[str, str]]
    ) -> List[SourceFingerprint]:
        """
        Fingerprint multiple sources.

        Args:
            sources: List of dicts with 'source_id' and 'text'

        Returns:
            List of SourceFingerprint objects
        """
        fingerprints = []

        for source in sources:
            fp = self.create_fingerprint(
                source_id=source.get("source_id", "unknown"),
                text=source["text"],
                metadata={k: v for k, v in source.items() if k not in ["source_id", "text"]},
            )
            fingerprints.append(fp)

        return fingerprints

    def record_verification(
        self,
        verification_id: str,
        answer_text: str,
        source_fingerprints: List[SourceFingerprint],
        confidence: float,
        trust_label: str,
    ) -> VerificationRecord:
        """
        Record a verification with fingerprints.

        Args:
            verification_id: Unique verification ID
            answer_text: Answer that was verified
            source_fingerprints: Fingerprints of sources used
            confidence: Confidence score
            trust_label: Trust label

        Returns:
            VerificationRecord
        """
        answer_hash = self.compute_hash(answer_text)
        source_hashes = [fp.hash for fp in source_fingerprints]

        record = VerificationRecord(
            verification_id=verification_id,
            answer_text=answer_text,
            answer_hash=answer_hash,
            source_fingerprints=source_hashes,
            confidence=confidence,
            trust_label=trust_label,
            created_at=datetime.now(),
            is_valid=True,
        )

        # Store record
        self._verifications[verification_id] = record

        # Index by source hashes
        for src_hash in source_hashes:
            if src_hash not in self._source_to_verifications:
                self._source_to_verifications[src_hash] = set()
            self._source_to_verifications[src_hash].add(verification_id)

        return record

    def check_source_changed(self, source_id: str, new_text: str) -> Dict[str, Any]:
        """
        Check if a source has changed.

        Args:
            source_id: Source identifier
            new_text: New source text

        Returns:
            Dict with:
                - changed: bool
                - old_hash: previous hash (if exists)
                - new_hash: current hash
                - affected_verifications: count of affected verifications
        """
        new_hash = self.compute_hash(new_text)

        # Find old fingerprint by source_id
        old_fingerprint = None
        for fp in self._fingerprints.values():
            if fp.source_id == source_id:
                old_fingerprint = fp
                break

        if not old_fingerprint:
            return {
                "changed": False,
                "old_hash": None,
                "new_hash": new_hash,
                "affected_verifications": 0,
                "reason": "no_previous_version",
            }

        old_hash = old_fingerprint.hash
        changed = old_hash != new_hash

        # Count affected verifications
        affected_count = len(self._source_to_verifications.get(old_hash, set()))

        return {
            "changed": changed,
            "old_hash": self.truncate_hash(old_hash),
            "new_hash": self.truncate_hash(new_hash),
            "old_hash_full": old_hash,
            "new_hash_full": new_hash,
            "affected_verifications": affected_count,
        }

    def invalidate_verifications_by_source(self, source_hash: str) -> List[str]:
        """
        Invalidate all verifications using a specific source.

        Args:
            source_hash: Hash of changed source

        Returns:
            List of invalidated verification IDs
        """
        affected_ids = self._source_to_verifications.get(source_hash, set())
        invalidated = []

        for vid in affected_ids:
            if vid in self._verifications:
                self._verifications[vid].is_valid = False
                invalidated.append(vid)

        return invalidated

    def update_source(
        self, source_id: str, new_text: str, metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Update a source and handle verification invalidation.

        Args:
            source_id: Source identifier
            new_text: New source text
            metadata: Optional metadata

        Returns:
            Dict with update results
        """
        # Check if changed
        change_result = self.check_source_changed(source_id, new_text)

        if not change_result["changed"]:
            return {
                "updated": False,
                "reason": "no_change",
                "invalidated_verifications": [],
            }

        # Create new fingerprint
        new_fingerprint = self.create_fingerprint(source_id, new_text, metadata)

        # Invalidate affected verifications
        invalidated = []
        if self.auto_invalidate and change_result["old_hash_full"]:
            invalidated = self.invalidate_verifications_by_source(
                change_result["old_hash_full"]
            )

        return {
            "updated": True,
            "old_hash": change_result["old_hash"],
            "new_hash": change_result["new_hash"],
            "invalidated_verifications": invalidated,
            "invalidated_count": len(invalidated),
        }

    def get_verification_status(self, verification_id: str) -> Optional[Dict[str, Any]]:
        """
        Get status of a verification.

        Args:
            verification_id: Verification ID

        Returns:
            Dict with status or None if not found
        """
        record = self._verifications.get(verification_id)
        if not record:
            return None

        return {
            "verification_id": verification_id,
            "is_valid": record.is_valid,
            "confidence": record.confidence,
            "trust_label": record.trust_label,
            "created_at": record.created_at.isoformat(),
            "source_count": len(record.source_fingerprints),
            "answer_hash": self.truncate_hash(record.answer_hash),
        }

    def get_audit_trail(self, source_id: str) -> List[Dict[str, Any]]:
        """
        Get audit trail for a source.

        Args:
            source_id: Source identifier

        Returns:
            List of verification records using this source
        """
        # Find all fingerprints for this source
        source_hashes = [
            fp.hash for fp in self._fingerprints.values() if fp.source_id == source_id
        ]

        # Find all verifications using these hashes
        verification_ids = set()
        for src_hash in source_hashes:
            verification_ids.update(self._source_to_verifications.get(src_hash, set()))

        # Get records
        records = []
        for vid in verification_ids:
            if vid in self._verifications:
                records.append(self._verifications[vid].to_dict())

        # Sort by date
        records.sort(key=lambda x: x["created_at"], reverse=True)

        return records

    def export_fingerprints(self) -> Dict[str, Any]:
        """Export all fingerprints to dict"""
        return {
            "fingerprints": [fp.to_dict() for fp in self._fingerprints.values()],
            "count": len(self._fingerprints),
            "exported_at": datetime.now().isoformat(),
        }

    def export_verifications(self, include_invalid: bool = False) -> Dict[str, Any]:
        """Export verification records"""
        records = [
            rec.to_dict()
            for rec in self._verifications.values()
            if include_invalid or rec.is_valid
        ]

        return {
            "verifications": records,
            "count": len(records),
            "exported_at": datetime.now().isoformat(),
        }

    def get_statistics(self) -> Dict[str, Any]:
        """Get tracker statistics"""
        total_verifications = len(self._verifications)
        valid_verifications = sum(
            1 for v in self._verifications.values() if v.is_valid
        )

        return {
            "total_fingerprints": len(self._fingerprints),
            "total_verifications": total_verifications,
            "valid_verifications": valid_verifications,
            "invalid_verifications": total_verifications - valid_verifications,
            "unique_sources": len(set(fp.source_id for fp in self._fingerprints.values())),
        }


def main() -> None:
    """Demo usage of fingerprint tracker"""
    print("🔐 Fingerprint Tracker Demo\n")

    tracker = FingerprintTracker(auto_invalidate=True)

    # Create source fingerprints
    sources = [
        {
            "source_id": "bgb_823",
            "text": "Wer vorsätzlich oder fahrlässig das Leben, den Körper, die Gesundheit verletzt...",
        },
        {
            "source_id": "bgb_276",
            "text": "Der Schuldner hat Vorsatz und Fahrlässigkeit zu vertreten...",
        },
    ]

    print("Creating source fingerprints...")
    fingerprints = tracker.fingerprint_sources(sources)
    for fp in fingerprints:
        print(f"  {fp.source_id}: {tracker.truncate_hash(fp.hash)}")

    # Record verification
    print("\nRecording verification...")
    record = tracker.record_verification(
        verification_id="ver_001",
        answer_text="Nach § 823 BGB haftet, wer vorsätzlich einen Schaden verursacht.",
        source_fingerprints=fingerprints,
        confidence=0.89,
        trust_label="✅ Verified",
    )
    print(f"  Verification ID: {record.verification_id}")
    print(f"  Confidence: {record.confidence}")
    print(f"  Trust Label: {record.trust_label}")

    # Update source (trigger invalidation)
    print("\n" + "=" * 60)
    print("Updating source bgb_823...")

    updated_text = "Wer vorsätzlich oder fahrlässig einen anderen schädigt... [GEÄNDERT]"
    update_result = tracker.update_source("bgb_823", updated_text)

    print(f"  Updated: {update_result['updated']}")
    print(f"  Old Hash: {update_result['old_hash']}")
    print(f"  New Hash: {update_result['new_hash']}")
    print(f"  Invalidated: {update_result['invalidated_count']} verifications")

    # Check verification status
    print("\nChecking verification status...")
    status = tracker.get_verification_status("ver_001")
    print(f"  Valid: {status['is_valid']}")
    print(f"  Confidence: {status['confidence']}")

    # Statistics
    print("\n" + "=" * 60)
    stats = tracker.get_statistics()
    print("\n📊 Tracker Statistics:")
    for key, value in stats.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
