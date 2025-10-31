"""
Tests for CheckpointManager - resumable pipeline with data persistence.

Tests cover:
- State save/load operations
- Data persistence (documents, normalized, chunks)
- Resume functionality
- Checkpoint management (list, delete)
- Error handling
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import json
import tempfile
import shutil
from datetime import datetime

from src.state.checkpoint_manager import CheckpointManager
from src.models.document import IngestionState
from src.exceptions import CheckpointCorruptedError


class TestCheckpointManager:
    """Test suite for CheckpointManager."""

    @pytest.fixture
    def temp_checkpoint_dir(self):
        """Create temporary directory for checkpoints."""
        temp_dir = Path(tempfile.mkdtemp())
        yield temp_dir
        # Cleanup after tests
        if temp_dir.exists():
            shutil.rmtree(temp_dir)

    @pytest.fixture
    def manager(self, temp_checkpoint_dir):
        """Create CheckpointManager instance for testing."""
        return CheckpointManager(checkpoint_dir=temp_checkpoint_dir)

    @pytest.fixture
    def sample_state(self) -> IngestionState:
        """Create sample ingestion state."""
        return {
            "run_id": "test-run-001",
            "start_time": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat(),
            "status": "running",
            "documents_fetched": 100,
            "documents_normalized": 95,
            "chunks_created": 500,
            "vectors_uploaded": 0,
            "last_openlegal_case_date": "2025-01-01",
            "last_openlegal_law_date": "2025-01-01",
            "last_eurlex_doc_id": None,
            "error_count": 0,
            "last_error": None,
        }

    @pytest.fixture
    def sample_documents(self):
        """Create sample legal documents."""
        return [
            {
                "doc_id": "doc-001",
                "title": "Test Document 1",
                "text": "This is a test document.",
                "url": "https://example.com/doc-001",
                "type": "case",
                "jurisdiction": "DE",
                "court": "BGH",
            },
            {
                "doc_id": "doc-002",
                "title": "Test Document 2",
                "text": "This is another test document.",
                "url": "https://example.com/doc-002",
                "type": "statute",
                "jurisdiction": "DE",
                "law": "BGB",
            },
        ]

    # ===== STATE MANAGEMENT TESTS =====

    def test_save_and_load_checkpoint(self, manager, sample_state):
        """Test saving and loading checkpoint state."""
        # Save checkpoint
        manager.save_checkpoint(sample_state)

        # Load checkpoint
        loaded_state = manager.load_checkpoint(sample_state["run_id"])

        assert loaded_state is not None
        assert loaded_state["run_id"] == sample_state["run_id"]
        assert loaded_state["documents_fetched"] == 100
        assert loaded_state["status"] == "running"

    def test_load_nonexistent_checkpoint(self, manager):
        """Test loading checkpoint that doesn't exist."""
        result = manager.load_checkpoint("nonexistent-run")
        assert result is None

    def test_create_initial_state(self, manager):
        """Test creating initial state for new run."""
        state = manager.create_initial_state(run_id="test-init")

        assert state["run_id"] == "test-init"
        assert state["status"] == "running"
        assert state["documents_fetched"] == 0
        assert state["chunks_created"] == 0
        assert state["error_count"] == 0

    def test_atomic_checkpoint_save(self, manager, sample_state):
        """Test that checkpoint saves are atomic (no partial writes)."""
        manager.save_checkpoint(sample_state)

        # Verify no .tmp files left behind
        run_dir = manager._get_run_dir(sample_state["run_id"])
        tmp_files = list(run_dir.glob("*.tmp"))
        assert len(tmp_files) == 0

        # Verify state.json exists and is valid
        state_file = manager._get_state_path(sample_state["run_id"])
        assert state_file.exists()

        with open(state_file, "r") as f:
            loaded = json.load(f)
        assert loaded["run_id"] == sample_state["run_id"]

    # ===== DATA PERSISTENCE TESTS =====

    def test_save_and_load_documents(self, manager, sample_documents):
        """Test saving and loading documents."""
        run_id = "test-docs"

        # Save documents
        manager.save_documents(run_id, sample_documents)

        # Load documents
        loaded_docs = manager.load_documents(run_id)

        assert len(loaded_docs) == len(sample_documents)
        assert loaded_docs[0]["doc_id"] == "doc-001"
        assert loaded_docs[1]["doc_id"] == "doc-002"

    def test_save_and_load_normalized(self, manager, sample_documents):
        """Test saving and loading normalized documents."""
        run_id = "test-normalized"

        # Save normalized documents
        manager.save_normalized(run_id, sample_documents)

        # Load normalized documents
        loaded = manager.load_normalized(run_id)

        assert len(loaded) == len(sample_documents)
        assert loaded[0]["title"] == "Test Document 1"

    def test_save_and_load_chunks(self, manager):
        """Test saving and loading chunks."""
        run_id = "test-chunks"

        chunks = [
            {
                "chunk_id": "doc-001_chunk_0",
                "text": "This is chunk 0",
                "chunk_index": 0,
                "total_chunks": 2,
            },
            {
                "chunk_id": "doc-001_chunk_1",
                "text": "This is chunk 1",
                "chunk_index": 1,
                "total_chunks": 2,
            },
        ]

        # Save chunks
        manager.save_chunks(run_id, chunks)

        # Load chunks
        loaded = manager.load_chunks(run_id)

        assert len(loaded) == 2
        assert loaded[0]["chunk_id"] == "doc-001_chunk_0"
        assert loaded[1]["chunk_index"] == 1

    def test_load_nonexistent_data_returns_empty(self, manager):
        """Test loading data that doesn't exist returns empty list."""
        docs = manager.load_documents("nonexistent")
        normalized = manager.load_normalized("nonexistent")
        chunks = manager.load_chunks("nonexistent")

        assert docs == []
        assert normalized == []
        assert chunks == []

    # ===== CHECKPOINT MANAGEMENT TESTS =====

    def test_can_resume_running_checkpoint(self, manager, sample_state):
        """Test that checkpoints with status 'running' can be resumed."""
        sample_state["status"] = "running"
        manager.save_checkpoint(sample_state)

        can_resume = manager.can_resume(sample_state["run_id"])
        assert can_resume is True

    def test_can_resume_failed_checkpoint(self, manager, sample_state):
        """Test that checkpoints with status 'failed' can be resumed."""
        sample_state["status"] = "failed"
        manager.save_checkpoint(sample_state)

        can_resume = manager.can_resume(sample_state["run_id"])
        assert can_resume is True

    def test_cannot_resume_completed_checkpoint(self, manager, sample_state):
        """Test that completed checkpoints cannot be resumed."""
        sample_state["status"] = "completed"
        manager.save_checkpoint(sample_state)

        can_resume = manager.can_resume(sample_state["run_id"])
        assert can_resume is False

    def test_list_checkpoints(self, manager, sample_state):
        """Test listing all checkpoints."""
        # Create multiple checkpoints
        manager.save_checkpoint(sample_state)

        state2 = sample_state.copy()
        state2["run_id"] = "test-run-002"
        manager.save_checkpoint(state2)

        # List checkpoints
        checkpoints = manager.list_checkpoints()

        assert len(checkpoints) == 2
        run_ids = [cp["run_id"] for cp in checkpoints]
        assert "test-run-001" in run_ids
        assert "test-run-002" in run_ids

    def test_delete_checkpoint(self, manager, sample_state):
        """Test deleting a checkpoint."""
        # Create checkpoint
        manager.save_checkpoint(sample_state)
        assert manager.load_checkpoint(sample_state["run_id"]) is not None

        # Delete checkpoint
        result = manager.delete_checkpoint(sample_state["run_id"])
        assert result is True

        # Verify it's gone
        assert manager.load_checkpoint(sample_state["run_id"]) is None

    def test_delete_nonexistent_checkpoint(self, manager):
        """Test deleting checkpoint that doesn't exist."""
        result = manager.delete_checkpoint("nonexistent")
        assert result is False

    def test_get_latest_checkpoint(self, manager):
        """Test getting the most recently updated checkpoint."""
        import time

        # Create first checkpoint
        state1 = manager.create_initial_state("run-001")
        manager.save_checkpoint(state1)

        # Wait a moment
        time.sleep(0.1)

        # Create second checkpoint (more recent)
        state2 = manager.create_initial_state("run-002")
        manager.save_checkpoint(state2)

        # Get latest
        latest = manager.get_latest_checkpoint()

        assert latest is not None
        assert latest["run_id"] == "run-002"

    # ===== DIRECTORY STRUCTURE TESTS =====

    def test_checkpoint_directory_structure(self, manager, sample_state, sample_documents):
        """Test that checkpoint directory structure is correct."""
        run_id = sample_state["run_id"]

        # Save all data
        manager.save_checkpoint(sample_state)
        manager.save_documents(run_id, sample_documents)
        manager.save_normalized(run_id, sample_documents)
        manager.save_chunks(run_id, [{"chunk_id": "test", "text": "test"}])

        # Verify directory structure
        run_dir = manager._get_run_dir(run_id)
        assert run_dir.exists()
        assert (run_dir / "state.json").exists()
        assert (run_dir / "documents.jsonl").exists()
        assert (run_dir / "normalized.jsonl").exists()
        assert (run_dir / "chunks.jsonl").exists()

    # ===== RESUME WORKFLOW TEST =====

    def test_full_resume_workflow(self, manager, sample_documents):
        """Test complete resume workflow simulating pipeline interruption."""
        run_id = "resume-test"

        # Simulate initial run
        state = manager.create_initial_state(run_id)

        # Step 1: Fetch documents
        manager.save_documents(run_id, sample_documents)
        state["documents_fetched"] = len(sample_documents)
        manager.save_checkpoint(state)

        # Step 2: Normalize documents
        manager.save_normalized(run_id, sample_documents)
        state["documents_normalized"] = len(sample_documents)
        manager.save_checkpoint(state)

        # SIMULATE CRASH HERE - pipeline interrupted

        # Resume: Load state
        resumed_state = manager.load_checkpoint(run_id)
        assert resumed_state is not None
        assert resumed_state["documents_fetched"] == 2
        assert resumed_state["documents_normalized"] == 2

        # Resume: Load documents (skip refetching)
        loaded_docs = manager.load_documents(run_id)
        assert len(loaded_docs) == 2

        # Resume: Load normalized (skip renormalizing)
        loaded_normalized = manager.load_normalized(run_id)
        assert len(loaded_normalized) == 2

        # Continue pipeline from where it left off
        # (chunking step would go here)


def test_checkpoint_manager_basic():
    """Basic smoke test that can run without pytest."""
    import time

    # Create temporary directory
    temp_dir = Path(tempfile.mkdtemp())

    try:
        manager = CheckpointManager(checkpoint_dir=temp_dir)

        # Test 1: Create initial state
        state = manager.create_initial_state(run_id="smoke-test-001")
        print(f"✓ Created initial state: {state['run_id']}")

        # Test 2: Save checkpoint
        manager.save_checkpoint(state)
        print(f"✓ Saved checkpoint")

        # Test 3: Update and save again
        state["documents_fetched"] = 100
        state["chunks_created"] = 500
        manager.save_checkpoint(state)
        print(f"✓ Updated checkpoint")

        # Test 4: Load checkpoint
        loaded = manager.load_checkpoint("smoke-test-001")
        assert loaded["documents_fetched"] == 100
        print(f"✓ Loaded checkpoint: {loaded['documents_fetched']} docs")

        # Test 5: List checkpoints
        checkpoints = manager.list_checkpoints()
        assert len(checkpoints) > 0
        print(f"✓ Found {len(checkpoints)} checkpoint(s)")

        # Test 6: Delete checkpoint
        manager.delete_checkpoint("smoke-test-001")
        print(f"✓ Deleted checkpoint")

        print("\n✅ All smoke tests passed!")

    finally:
        # Cleanup
        if temp_dir.exists():
            shutil.rmtree(temp_dir)


if __name__ == "__main__":
    # Run basic smoke test when executed directly
    test_checkpoint_manager_basic()
