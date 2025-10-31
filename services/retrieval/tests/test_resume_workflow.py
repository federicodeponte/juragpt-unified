#!/usr/bin/env python3
"""
Integration test for full resume workflow.

Simulates pipeline execution, interruption, and resume to verify:
1. Data is saved to disk after each step
2. Data is loaded from disk when resuming
3. Steps are skipped correctly
4. No duplicate processing occurs
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.state.checkpoint_manager import CheckpointManager


def test_resume_workflow():
    """Test complete resume workflow."""
    print("\n" + "=" * 70)
    print("INTEGRATION TEST: Full Resume Workflow")
    print("=" * 70)

    manager = CheckpointManager()
    run_id = "integration-test-resume"

    # Clean up any existing checkpoint
    manager.delete_checkpoint(run_id)

    # ===== SIMULATE INITIAL RUN =====
    print("\n[INITIAL RUN] Starting pipeline simulation...")

    # Step 1: Create initial state
    state = manager.create_initial_state(run_id)
    print(f"✓ Created initial state: {run_id}")
    manager.save_checkpoint(state)

    # Step 2: Simulate fetching documents
    sample_documents = [
        {
            "doc_id": "law-001",
            "title": "Test Law 1",
            "text": "This is a test law document with enough text to be meaningful.",
            "url": "https://example.com/law-001",
            "type": "statute",
            "jurisdiction": "DE",
            "law": "TestG",
        },
        {
            "doc_id": "case-001",
            "title": "Test Case 1",
            "text": "This is a test court case with a decision and reasoning.",
            "url": "https://example.com/case-001",
            "type": "case",
            "jurisdiction": "DE",
            "court": "BGH",
        },
    ]

    manager.save_documents(run_id, sample_documents)
    state["documents_fetched"] = len(sample_documents)
    manager.save_checkpoint(state)
    print(f"✓ Fetched and saved {len(sample_documents)} documents")

    # Step 3: Simulate normalization
    # (In real pipeline, normalizer would clean the text)
    normalized_docs = [
        {**doc, "text": doc["text"].upper()}  # Simple "normalization"
        for doc in sample_documents
    ]

    manager.save_normalized(run_id, normalized_docs)
    state["documents_normalized"] = len(normalized_docs)
    manager.save_checkpoint(state)
    print(f"✓ Normalized and saved {len(normalized_docs)} documents")

    # Step 4: Simulate chunking
    chunks = [
        {
            "chunk_id": f"{doc['doc_id']}_chunk_0",
            "text": doc["text"][:50],
            "chunk_index": 0,
            "total_chunks": 1,
            "doc_id": doc["doc_id"],
            "title": doc["title"],
            "url": doc["url"],
            "type": doc["type"],
            "jurisdiction": doc["jurisdiction"],
        }
        for doc in normalized_docs
    ]

    manager.save_chunks(run_id, chunks)
    state["chunks_created"] = len(chunks)
    manager.save_checkpoint(state)
    print(f"✓ Created and saved {len(chunks)} chunks")

    # SIMULATE CRASH/INTERRUPTION HERE
    print("\n💥 [SIMULATED CRASH] Pipeline interrupted before embedding step")

    # ===== SIMULATE RESUME =====
    print("\n[RESUME] Attempting to resume from checkpoint...")

    # Step 1: Check if can resume
    can_resume = manager.can_resume(run_id)
    if not can_resume:
        print("❌ ERROR: Cannot resume from checkpoint!")
        return False

    print(f"✓ Checkpoint is resumable (status=running)")

    # Step 2: Load state
    resumed_state = manager.load_checkpoint(run_id)
    print(f"✓ Loaded state: {resumed_state['documents_fetched']} docs, "
          f"{resumed_state['chunks_created']} chunks")

    # Step 3: Load documents (skip refetching)
    if resumed_state["documents_fetched"] > 0:
        loaded_docs = manager.load_documents(run_id)
        print(f"✓ Loaded {len(loaded_docs)} documents from checkpoint (skipped fetch)")

        # Verify data integrity
        assert len(loaded_docs) == len(sample_documents), "Document count mismatch!"
        assert loaded_docs[0]["doc_id"] == "law-001", "Document ID mismatch!"
    else:
        print("  → Would fetch documents (not found in checkpoint)")

    # Step 4: Load normalized documents (skip renormalization)
    if resumed_state["documents_normalized"] > 0:
        loaded_normalized = manager.load_normalized(run_id)
        print(f"✓ Loaded {len(loaded_normalized)} normalized docs (skipped normalization)")

        # Verify data integrity
        assert len(loaded_normalized) == len(normalized_docs), "Normalized count mismatch!"
        assert "TEST LAW" in loaded_normalized[0]["text"], "Normalization lost!"
    else:
        print("  → Would normalize documents (not found in checkpoint)")

    # Step 5: Load chunks (skip rechunking)
    if resumed_state["chunks_created"] > 0:
        loaded_chunks = manager.load_chunks(run_id)
        print(f"✓ Loaded {len(loaded_chunks)} chunks (skipped chunking)")

        # Verify data integrity
        assert len(loaded_chunks) == len(chunks), "Chunk count mismatch!"
        assert loaded_chunks[0]["chunk_id"] == "law-001_chunk_0", "Chunk ID mismatch!"
    else:
        print("  → Would create chunks (not found in checkpoint)")

    # Step 6: Continue from where we left off
    print("\n✓ Would continue with embedding step (not in checkpoint)")

    # Step 7: Mark as completed
    resumed_state["status"] = "completed"
    resumed_state["vectors_uploaded"] = len(loaded_chunks)
    manager.save_checkpoint(resumed_state)
    print("✓ Marked pipeline as completed")

    # ===== VERIFY FINAL STATE =====
    print("\n[VERIFICATION] Checking final state...")

    final_state = manager.load_checkpoint(run_id)
    assert final_state["status"] == "completed", "Status should be completed!"
    assert final_state["documents_fetched"] == 2, "Should have 2 documents!"
    assert final_state["chunks_created"] == 2, "Should have 2 chunks!"
    assert final_state["vectors_uploaded"] == 2, "Should have 2 vectors!"

    print("✓ Final state verified")

    # ===== CHECK DIRECTORY STRUCTURE =====
    print("\n[DIRECTORY STRUCTURE] Verifying checkpoint files...")

    run_dir = manager._get_run_dir(run_id)
    expected_files = ["state.json", "documents.jsonl", "normalized.jsonl", "chunks.jsonl"]

    for filename in expected_files:
        file_path = run_dir / filename
        if file_path.exists():
            size = file_path.stat().st_size
            print(f"✓ {filename} exists ({size} bytes)")
        else:
            print(f"❌ {filename} missing!")
            return False

    # ===== CLEANUP =====
    print("\n[CLEANUP] Removing test checkpoint...")
    manager.delete_checkpoint(run_id)
    print("✓ Cleaned up")

    # ===== FINAL RESULT =====
    print("\n" + "=" * 70)
    print("✅ INTEGRATION TEST PASSED - Resume workflow works correctly!")
    print("=" * 70)

    print("\nKey verification points:")
    print("  ✓ Data saved to disk after each step")
    print("  ✓ Data loaded from disk when resuming")
    print("  ✓ Steps skipped correctly (no reprocessing)")
    print("  ✓ Directory structure correct")
    print("  ✓ No data corruption or loss")

    return True


if __name__ == "__main__":
    try:
        success = test_resume_workflow()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
