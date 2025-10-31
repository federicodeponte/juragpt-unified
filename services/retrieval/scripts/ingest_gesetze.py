#!/usr/bin/env python3
"""
German Federal Laws ETL pipeline with checkpointing support.

This is a separate ingestion pipeline for German federal laws from the
kmein/gesetze GitHub repository, running alongside the EUR-Lex pipeline.

Pipeline stages:
1. Load German laws from GitHub repository
2. Normalize text
3. Chunk documents
4. Generate embeddings
5. Upsert to Qdrant

Features:
- Resumable pipeline with automatic checkpointing
- Atomic state saves after each major step
- Resume from failed runs using --resume <run_id>
- Uses separate checkpoint directory from other pipelines

Usage:
    # New run (100 laws for testing)
    python scripts/ingest_gesetze.py --limit 100

    # Full dataset (~6,594 laws)
    python scripts/ingest_gesetze.py --limit 6594

    # Resume failed run
    python scripts/ingest_gesetze.py --resume 2025-10-29T21-00-00

    # List checkpoints
    python scripts/ingest_gesetze.py --list-checkpoints
"""

import sys
import argparse
import logging
import time
import signal
import json
from pathlib import Path
from datetime import datetime
from typing import Optional
from contextlib import contextmanager
import modal

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.crawlers.gesetze_github import GesetzeGitHubCrawler
from src.processing.normalizer import TextNormalizer
from src.processing.chunker import TextChunker
from src.embedding.embedder import LegalTextEmbedder
from src.storage.qdrant_client import JuraGPTQdrantClient
from src.state.checkpoint_manager import CheckpointManager
from src.models.document import IngestionState

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# Timeout context manager for production-grade error handling
@contextmanager
def timeout(seconds, error_message="Operation timed out"):
    """
    Context manager for timeout protection.

    Usage:
        with timeout(180):
            # code that might hang
    """
    def timeout_handler(signum, frame):
        raise TimeoutError(error_message)

    # Set signal handler and alarm
    old_handler = signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(seconds)

    try:
        yield
    finally:
        # Disable alarm and restore old handler
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)


class GesetzeIngestionPipeline:
    """ETL pipeline for German federal laws from kmein/gesetze repository."""

    def __init__(self, checkpoint_dir: Path = Path("data/checkpoints_gesetze")):
        """
        Initialize German laws pipeline components.

        Args:
            checkpoint_dir: Directory for checkpoint files
        """
        logger.info("Initializing German Laws ETL pipeline...")

        self.gesetze_crawler = GesetzeGitHubCrawler()
        self.normalizer = TextNormalizer()
        self.chunker = TextChunker()
        self.embedder = LegalTextEmbedder()
        self.qdrant_client = JuraGPTQdrantClient()
        self.checkpoint_manager = CheckpointManager(checkpoint_dir=checkpoint_dir)

        # State tracking
        self.state: Optional[IngestionState] = None
        self.all_documents = []
        self.normalized_docs = []
        self.chunks = []
        self.embeddings = []
        self.skipped_documents = []  # Track documents that timeout or fail

        logger.info("German laws pipeline components initialized")

    def _save_checkpoint(self):
        """Save current pipeline state to checkpoint."""
        self.checkpoint_manager.save_checkpoint(self.state)

    def _convert_to_standard_format(self, gesetze_docs: list) -> list:
        """
        Convert German laws format to pipeline format.

        GesetzeGitHubCrawler already returns StatuteDocument format,
        just need to ensure 'text' field for normalizer.

        Args:
            gesetze_docs: List of StatuteDocument from crawler

        Returns:
            List of documents in standard format with 'text' field
        """
        formatted_docs = []
        for doc in gesetze_docs:
            # Convert 'content' to 'text' for normalizer compatibility
            formatted_doc = {
                'source': doc['source'],
                'type': doc['type'],
                'doc_id': doc['slug'],  # Use slug as document ID (e.g., "BGB")
                'slug': doc['slug'],
                'title': doc['title'],
                'text': doc['content'],  # Normalizer expects 'text'
                'url': doc['url'],
                'created_date': doc['created_date'],
                'jurisdiction': 'DE',  # German federal laws
                'law': doc['slug']  # Law abbreviation (e.g., "BGB", "StGB")
            }
            formatted_docs.append(formatted_doc)
        return formatted_docs

    def run(
        self,
        limit: int = 100,
        force_recreate_collection: bool = False,
        resume_from: Optional[str] = None,
    ):
        """
        Run the German laws ETL pipeline with checkpointing.

        Args:
            limit: Maximum number of laws to process
            force_recreate_collection: Force recreate Qdrant collection
            resume_from: Optional run_id to resume from checkpoint
        """
        start_time = time.time()

        try:
            # Initialize or resume state
            if resume_from:
                logger.info(f"Attempting to resume from checkpoint: {resume_from}")
                self.state = self.checkpoint_manager.load_checkpoint(resume_from)
                if not self.state:
                    raise ValueError(f"No checkpoint found for run_id: {resume_from}")
                logger.info(f"Resumed from checkpoint: {self.state['last_updated']}")
            else:
                # Create new run
                run_id = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
                self.state = self.checkpoint_manager.create_initial_state(run_id)
                logger.info(f"Starting new German laws pipeline run: {run_id}")

            # Step 1: Initialize Qdrant collection
            if self.state["vectors_uploaded"] == 0:
                logger.info("\n=== Step 1: Initialize Qdrant Collection ===")
                self.qdrant_client.create_collection(
                    vector_size=self.embedder.embedding_dim,
                    force=force_recreate_collection
                )
                self._save_checkpoint()

            # Step 2: Fetch German laws (or load from checkpoint)
            if self.state["documents_fetched"] == 0:
                logger.info("\n=== Step 2: Load German Federal Laws ===")
                logger.info(f"Loading up to {limit} laws from kmein/gesetze repository...")

                # Load laws from GitHub repo (don't update - already cloned)
                gesetze_docs = self.gesetze_crawler.fetch_laws(
                    limit=limit,
                    update_repo=False  # Repo already cloned in Phase 1
                )
                logger.info(f"Loaded {len(gesetze_docs)} German laws")

                # Convert to standard format
                self.all_documents = self._convert_to_standard_format(gesetze_docs)
                logger.info(f"Converted {len(self.all_documents)} documents to standard format")

                if not self.all_documents:
                    logger.error("No documents loaded. Aborting pipeline.")
                    self.state["status"] = "failed"
                    self._save_checkpoint()
                    return

                # Save documents to checkpoint
                self.checkpoint_manager.save_documents(
                    self.state["run_id"],
                    self.all_documents
                )

                # Update state
                self.state["documents_fetched"] = len(self.all_documents)
                self._save_checkpoint()
            else:
                # Resume: load documents from checkpoint
                logger.info(f"\n=== Step 2: Loading {self.state['documents_fetched']} documents from checkpoint ===")
                self.all_documents = self.checkpoint_manager.load_documents(self.state["run_id"])
                if not self.all_documents:
                    logger.error("Failed to load documents from checkpoint!")
                    self.state["status"] = "failed"
                    self._save_checkpoint()
                    return

            # Step 3: Normalize text
            logger.info("\n=== Step 3: Normalize Text ===")
            self.normalizer.normalize_documents(self.all_documents)
            self.normalized_docs = self.all_documents
            logger.info(f"Normalized {len(self.normalized_docs)} documents")

            # Save normalized documents
            # Note: CheckpointManager doesn't have save_normalized_documents,
            # but normalization modifies docs in-place, so just save checkpoint
            self._save_checkpoint()

            # Step 4: Chunk documents (batched) with timeout protection
            if self.state["chunks_created"] == 0:
                logger.info("\n=== Step 4: Chunk Documents (Batched Processing with Timeout Protection) ===")

                # Process in batches to save checkpoints
                # German laws are MUCH larger than EUR-Lex docs (some are 1.5MB+)
                # so we use smaller batches to avoid memory issues and timeouts
                batch_size = 100  # Chunk 100 laws at a time (vs 1000 for EUR-Lex)
                num_batches = (len(self.normalized_docs) + batch_size - 1) // batch_size

                # Timeout configuration
                BATCH_TIMEOUT = 1800  # 30 minutes per batch
                DOC_TIMEOUT = 300     # 5 minutes per document (BGB is huge)

                logger.info(f"Chunking {len(self.normalized_docs)} documents in {num_batches} batches")
                logger.info(f"Timeout protection: {BATCH_TIMEOUT}s per batch, {DOC_TIMEOUT}s per document")

                all_chunks = []
                for batch_idx in range(num_batches):
                    start_idx = batch_idx * batch_size
                    end_idx = min((batch_idx + 1) * batch_size, len(self.normalized_docs))
                    batch_docs = self.normalized_docs[start_idx:end_idx]

                    # Wrap entire batch in timeout protection
                    try:
                        with timeout(BATCH_TIMEOUT, f"Batch {batch_idx + 1} timed out after {BATCH_TIMEOUT}s"):
                            batch_chunks = []

                            # Process each document with individual timeout
                            for doc_idx, doc in enumerate(batch_docs):
                                try:
                                    with timeout(DOC_TIMEOUT, f"Document {doc.get('slug', 'unknown')} timed out"):
                                        # Chunk single document
                                        doc_chunks = self.chunker.chunk_documents([doc])
                                        batch_chunks.extend(doc_chunks)

                                        # Log progress every 10 documents
                                        if (doc_idx + 1) % 10 == 0:
                                            logger.info(
                                                f"  Batch {batch_idx + 1}: Processed {doc_idx + 1}/{len(batch_docs)} docs, "
                                                f"{len(batch_chunks)} chunks so far"
                                            )

                                except TimeoutError as e:
                                    doc_slug = doc.get('slug', 'unknown')
                                    logger.warning(f"⏱️  TIMEOUT: {doc_slug} - {e}")
                                    self.skipped_documents.append({
                                        'slug': doc_slug,
                                        'title': doc.get('title', 'Unknown'),
                                        'reason': 'timeout',
                                        'batch': batch_idx + 1,
                                        'error': str(e)
                                    })
                                    continue  # Skip this document and continue with next

                                except Exception as e:
                                    doc_slug = doc.get('slug', 'unknown')
                                    logger.error(f"❌ ERROR: {doc_slug} - {e}")
                                    self.skipped_documents.append({
                                        'slug': doc_slug,
                                        'title': doc.get('title', 'Unknown'),
                                        'reason': 'error',
                                        'batch': batch_idx + 1,
                                        'error': str(e)
                                    })
                                    continue  # Skip this document and continue with next

                            all_chunks.extend(batch_chunks)

                            logger.info(
                                f"✓ Batch {batch_idx + 1}/{num_batches}: "
                                f"Processed docs {start_idx + 1}-{end_idx}/{len(self.normalized_docs)}, "
                                f"created {len(batch_chunks)} chunks (total: {len(all_chunks)} chunks)"
                            )

                    except TimeoutError as e:
                        logger.error(f"🚨 BATCH TIMEOUT: Batch {batch_idx + 1} exceeded {BATCH_TIMEOUT}s - {e}")
                        logger.info(f"Skipping remaining documents in batch {batch_idx + 1}")
                        # Continue to next batch
                        continue

                    # Save checkpoint after each batch (even if some docs were skipped)
                    self.checkpoint_manager.save_chunks(self.state["run_id"], all_chunks)
                    self.state["chunks_created"] = len(all_chunks)
                    self._save_checkpoint()
                    logger.info(f"✓ Saved batch to disk: {len(all_chunks)} total chunks created so far")

                self.chunks = all_chunks
                logger.info(f"Total chunks created: {len(self.chunks)}")

                # Log skipped documents summary
                if self.skipped_documents:
                    logger.warning(f"⚠️  Skipped {len(self.skipped_documents)} documents due to timeouts/errors")
                    # Save skipped documents to file
                    skipped_path = Path(self.checkpoint_manager.checkpoint_dir) / self.state["run_id"] / "skipped_documents.json"
                    with open(skipped_path, "w") as f:
                        json.dump(self.skipped_documents, f, indent=2)
                    logger.info(f"📝 Skipped documents logged to: {skipped_path}")

            else:
                # Resume: load chunks from checkpoint
                logger.info(f"\n=== Step 4: Loading {self.state['chunks_created']} chunks from checkpoint ===")
                self.chunks = self.checkpoint_manager.load_chunks(self.state["run_id"])
                if not self.chunks:
                    logger.error("Failed to load chunks from checkpoint!")
                    self.state["status"] = "failed"
                    self._save_checkpoint()
                    return

            # Step 5: Generate embeddings & upload (batched)
            logger.info("\n=== Step 5: Generate Embeddings & Upload (Batched Processing) ===")

            vectors_uploaded = self.state["vectors_uploaded"]
            remaining_chunks = self.chunks[vectors_uploaded:]

            if not remaining_chunks:
                logger.info("All chunks already uploaded!")
            else:
                # Use same batch size as EUR-Lex for embedding/upload
                # (this part is fast, chunking was the bottleneck)
                batch_size = 1000  # Process 1000 chunks at a time
                num_batches = (len(remaining_chunks) + batch_size - 1) // batch_size

                logger.info(f"Processing {len(remaining_chunks)} chunks in batches of {batch_size}")

                # Lookup Modal GPU function once before loop
                embed_func = modal.Function.from_name("juragpt-embedder", "embed_batch_gpu")

                for batch_idx in range(num_batches):
                    start_idx = batch_idx * batch_size
                    end_idx = min((batch_idx + 1) * batch_size, len(remaining_chunks))
                    batch_chunks = remaining_chunks[start_idx:end_idx]

                    # Generate embeddings on GPU via Modal (15-30x faster than CPU)
                    texts = [chunk["text"] for chunk in batch_chunks]
                    batch_embeddings = embed_func.remote(texts)

                    # Upload to Qdrant (optimized batch size for 5-10x speedup)
                    self.qdrant_client.upsert_chunks(batch_chunks, batch_embeddings, batch_size=1000)

                    # Update state
                    vectors_uploaded += len(batch_chunks)
                    self.state["vectors_uploaded"] = vectors_uploaded
                    self._save_checkpoint()

                    progress = (vectors_uploaded / len(self.chunks)) * 100
                    logger.info(f"✓ Uploaded batch: {vectors_uploaded}/{len(self.chunks)} vectors ({progress:.1f}%)")

            # Mark as completed
            self.state["status"] = "completed"
            self._save_checkpoint()

            # Summary
            duration = time.time() - start_time
            logger.info("\n" + "=" * 80)
            logger.info("🎉 German Laws Pipeline Completed Successfully!")
            logger.info("=" * 80)
            logger.info(f"Run ID: {self.state['run_id']}")
            logger.info(f"Documents processed: {len(self.all_documents)}")
            logger.info(f"Chunks created: {len(self.chunks)}")
            logger.info(f"Vectors uploaded: {self.state['vectors_uploaded']}")
            logger.info(f"Total duration: {duration / 60:.1f} minutes")
            logger.info("=" * 80)

        except KeyboardInterrupt:
            logger.warning("\n⚠️ Pipeline interrupted by user")
            self.state["status"] = "interrupted"
            self._save_checkpoint()
            logger.info(f"Progress saved. Resume with: --resume {self.state['run_id']}")

        except Exception as e:
            logger.error(f"\n❌ Pipeline failed with error: {e}")
            logger.exception(e)
            self.state["status"] = "failed"
            self.state["last_error"] = str(e)
            self._save_checkpoint()
            raise


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Ingest German federal laws into Qdrant vector database"
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Maximum number of laws to process (default: 100)"
    )
    parser.add_argument(
        "--force-recreate",
        action="store_true",
        help="Force recreate Qdrant collection (WARNING: deletes existing data)"
    )
    parser.add_argument(
        "--resume",
        type=str,
        help="Resume from checkpoint (provide run_id)"
    )
    parser.add_argument(
        "--list-checkpoints",
        action="store_true",
        help="List available checkpoints and exit"
    )

    args = parser.parse_args()

    # List checkpoints if requested
    if args.list_checkpoints:
        checkpoint_manager = CheckpointManager(checkpoint_dir=Path("data/checkpoints_gesetze"))
        checkpoints = checkpoint_manager.list_checkpoints()

        if not checkpoints:
            print("No checkpoints found.")
        else:
            print("\nAvailable checkpoints:")
            print("-" * 80)
            for cp in checkpoints:
                print(f"Run ID: {cp['run_id']}")
                print(f"  Status: {cp['status']}")
                print(f"  Last updated: {cp['last_updated']}")
                print(f"  Documents: {cp['documents_fetched']}")
                print(f"  Chunks: {cp['chunks_created']}")
                print(f"  Vectors: {cp['vectors_uploaded']}")
                print("-" * 80)
        return

    # Run pipeline
    pipeline = GesetzeIngestionPipeline()
    pipeline.run(
        limit=args.limit,
        force_recreate_collection=args.force_recreate,
        resume_from=args.resume
    )


if __name__ == "__main__":
    main()
