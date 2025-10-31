# -*- coding: utf-8 -*-
"""
Unit tests for FingerprintTracker module.
"""

import pytest
from datetime import datetime
from auditor.core.fingerprint_tracker import (
    FingerprintTracker,
    SourceFingerprint,
    VerificationRecord,
)


class TestSourceFingerprint:
    """Test SourceFingerprint dataclass."""

    def test_creation(self):
        """Test creating a source fingerprint."""
        fp = SourceFingerprint(
            source_id="test_001",
            text="Sample text",
            hash="abc123",
            created_at=datetime.now(),
            metadata={"type": "law"},
        )
        assert fp.source_id == "test_001"
        assert fp.text == "Sample text"
        assert fp.hash == "abc123"
        assert fp.metadata["type"] == "law"

    def test_to_dict(self):
        """Test conversion to dictionary."""
        fp = SourceFingerprint(
            source_id="test_001",
            text="Sample text",
            hash="abc123",
            created_at=datetime(2024, 1, 1, 12, 0, 0),
            metadata={"type": "law"},
        )
        d = fp.to_dict()

        assert d["source_id"] == "test_001"
        assert d["text"] == "Sample text"
        assert d["hash"] == "abc123"
        assert isinstance(d["created_at"], str)
        assert d["metadata"]["type"] == "law"

    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {
            "source_id": "test_001",
            "text": "Sample text",
            "hash": "abc123",
            "created_at": "2024-01-01T12:00:00",
            "metadata": {"type": "law"},
        }
        fp = SourceFingerprint.from_dict(data)

        assert fp.source_id == "test_001"
        assert fp.text == "Sample text"
        assert isinstance(fp.created_at, datetime)


class TestVerificationRecord:
    """Test VerificationRecord dataclass."""

    def test_creation(self):
        """Test creating a verification record."""
        rec = VerificationRecord(
            verification_id="ver_001",
            answer_text="Answer text",
            answer_hash="hash123",
            source_fingerprints=["fp1", "fp2"],
            confidence=0.85,
            trust_label="✅ Verified",
            created_at=datetime.now(),
            is_valid=True,
        )
        assert rec.verification_id == "ver_001"
        assert len(rec.source_fingerprints) == 2
        assert rec.confidence == 0.85

    def test_to_dict(self):
        """Test conversion to dictionary."""
        rec = VerificationRecord(
            verification_id="ver_001",
            answer_text="Answer",
            answer_hash="hash",
            source_fingerprints=["fp1"],
            confidence=0.85,
            trust_label="✅ Verified",
            created_at=datetime(2024, 1, 1, 12, 0, 0),
        )
        d = rec.to_dict()

        assert d["verification_id"] == "ver_001"
        assert d["confidence"] == 0.85
        assert isinstance(d["created_at"], str)


class TestFingerprintTracker:
    """Test FingerprintTracker functionality."""

    @pytest.fixture
    def tracker(self):
        """Create a fresh tracker instance."""
        return FingerprintTracker()

    def test_initialization(self):
        """Test tracker initialization."""
        tracker = FingerprintTracker(
            algorithm="sha256",
            truncate_length=12,
            auto_invalidate=False,
        )
        assert tracker.algorithm == "sha256"
        assert tracker.truncate_length == 12
        assert tracker.auto_invalidate is False

    def test_compute_hash(self, tracker):
        """Test hash computation."""
        text = "Sample text for hashing"
        hash1 = tracker.compute_hash(text)

        # Should return consistent hash
        assert isinstance(hash1, str)
        assert len(hash1) == 64  # SHA-256 hex digest length

        # Same text should produce same hash
        hash2 = tracker.compute_hash(text)
        assert hash1 == hash2

        # Different text should produce different hash
        hash3 = tracker.compute_hash("Different text")
        assert hash1 != hash3

    def test_compute_hash_unicode(self, tracker):
        """Test hash with Unicode characters."""
        text = "Text with umlauts: äöü and symbols: § ©"
        hash_val = tracker.compute_hash(text)

        # Should handle Unicode properly
        assert isinstance(hash_val, str)
        assert len(hash_val) == 64

    def test_truncate_hash(self, tracker):
        """Test hash truncation."""
        hash_val = "abcdef1234567890" * 4  # 64 chars
        truncated = tracker.truncate_hash(hash_val)

        assert len(truncated) == tracker.truncate_length
        assert truncated == hash_val[:tracker.truncate_length]

    def test_create_fingerprint(self, tracker):
        """Test creating a source fingerprint."""
        fp = tracker.create_fingerprint(
            source_id="bgb_823",
            text="Sample legal text",
            metadata={"law": "BGB", "section": "§ 823"},
        )

        assert isinstance(fp, SourceFingerprint)
        assert fp.source_id == "bgb_823"
        assert fp.text == "Sample legal text"
        assert len(fp.hash) == 64
        assert fp.metadata["law"] == "BGB"
        assert isinstance(fp.created_at, datetime)

        # Should be stored in tracker
        assert fp.hash in tracker._fingerprints

    def test_create_fingerprint_no_metadata(self, tracker):
        """Test creating fingerprint without metadata."""
        fp = tracker.create_fingerprint(
            source_id="test_id",
            text="Test text",
        )

        assert fp.metadata == {}

    def test_fingerprint_sources_batch(self, tracker):
        """Test batch fingerprinting of sources."""
        sources = [
            {
                "source_id": "src_1",
                "text": "First source text",
                "extra_metadata": {"type": "law"},
            },
            {
                "source_id": "src_2",
                "text": "Second source text",
                "extra_metadata": {"type": "case"},
            },
        ]

        # Assuming fingerprint_sources method exists
        # This would need to be implemented in the actual class
        # For now, test individual creation
        fps = [
            tracker.create_fingerprint(
                source_id=src["source_id"],
                text=src["text"],
                metadata=src.get("extra_metadata"),
            )
            for src in sources
        ]

        assert len(fps) == 2
        assert all(isinstance(fp, SourceFingerprint) for fp in fps)

    def test_get_fingerprint(self, tracker):
        """Test retrieving a fingerprint by hash."""
        fp_created = tracker.create_fingerprint(
            source_id="test_id",
            text="Test text",
        )

        # Should be able to retrieve it
        fp_retrieved = tracker._fingerprints.get(fp_created.hash)
        assert fp_retrieved is not None
        assert fp_retrieved.source_id == "test_id"

    def test_detect_source_change(self, tracker):
        """Test detecting when source text changes."""
        source_id = "bgb_823"
        original_text = "Original legal text"
        modified_text = "Modified legal text"

        # Create original fingerprint
        fp1 = tracker.create_fingerprint(source_id, original_text)

        # Create fingerprint for modified text
        fp2 = tracker.create_fingerprint(source_id, modified_text)

        # Hashes should be different
        assert fp1.hash != fp2.hash

    def test_fingerprint_consistency(self, tracker):
        """Test that same text always produces same fingerprint."""
        text = "Consistent text for testing"

        fp1 = tracker.create_fingerprint("id1", text)
        fp2 = tracker.create_fingerprint("id2", text)

        # Different IDs, same text should produce same hash
        assert fp1.hash == fp2.hash

    def test_empty_text_fingerprint(self, tracker):
        """Test fingerprinting empty text."""
        fp = tracker.create_fingerprint("empty_id", "")

        assert fp.text == ""
        assert isinstance(fp.hash, str)
        assert len(fp.hash) == 64

    def test_large_text_fingerprint(self, tracker):
        """Test fingerprinting large text."""
        large_text = "Lorem ipsum " * 1000  # ~12KB
        fp = tracker.create_fingerprint("large_id", large_text)

        assert isinstance(fp.hash, str)
        assert len(fp.hash) == 64  # Hash length constant regardless of input
