#!/usr/bin/env python3
"""
EUR-Lex ETL pipeline with checkpointing support.

This is a separate ingestion pipeline for EUR-Lex documents,
running alongside the main OpenLegalData pipeline.

Pipeline stages:
1. Load EUR-Lex documents from dataset
2. Normalize text
3. Chunk documents
4. Generate embeddings
5. Upsert to Qdrant

Features:
- Resumable pipeline with automatic checkpointing
- Atomic state saves after each major step
- Resume from failed runs using --resume <run_id>
- Uses separate checkpoint directory from main pipeline

Usage:
    # New run (1000 documents)
    python scripts/ingest_eurlex.py --limit 1000

    # Full dataset (57,000 documents)
    python scripts/ingest_eurlex.py --limit 57000

    # Resume failed run
    python scripts/ingest_eurlex.py --resume 2025-10-29T15-00-00

    # List checkpoints
    python scripts/ingest_eurlex.py --list-checkpoints
"""

import sys
import argparse
import logging
import time
import hashlib
import json
import modal
from pathlib import Path
from datetime import datetime
from typing import Optional

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.crawlers.eurlex_dataset import EURLexDataset
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


class EURLexPipeline:
    """ETL pipeline specifically for EUR-Lex documents."""

    def __init__(self, checkpoint_dir: Path = Path("data/checkpoints_eurlex")):
        """
        Initialize EUR-Lex pipeline components.

        Args:
            checkpoint_dir: Directory for EUR-Lex checkpoint files
        """
        logger.info("Initializing EUR-Lex ETL pipeline...")

        self.eurlex_loader = EURLexDataset()
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

        logger.info("EUR-Lex pipeline components initialized")

    def _save_checkpoint(self):
        """Save current pipeline state to checkpoint."""
        self.checkpoint_manager.save_checkpoint(self.state)

    def _convert_eurlex_to_standard_format(self, eurlex_docs: list) -> list:
        """
        Convert EUR-Lex document format to our standard format.

        EUR-Lex format: {doc_id, title, text, url, type, jurisdiction, concepts}
        Our format: {source, type, doc_id, slug, title, text, url, created_date}

        Args:
            eurlex_docs: List of EUR-Lex documents

        Returns:
            List of documents in standard format
        """
        formatted_docs = []
        for doc in eurlex_docs:
            formatted_doc = {
                'source': 'eurlex',
                'type': doc.get('type', 'eu_law'),
                'doc_id': doc['doc_id'],
                'slug': doc['doc_id'],
                'title': doc['title'],
                'text': doc['text'],  # Keep as 'text' for normalizer
                'url': doc['url'],
                'created_date': datetime.now().isoformat(),
                'jurisdiction': doc.get('jurisdiction', 'EU'),
                'concepts': doc.get('concepts', [])[:5]  # Limit to 5 concepts
            }
            formatted_docs.append(formatted_doc)
        return formatted_docs

    def run(
        self,
        limit: int = 1000,
        force_recreate_collection: bool = False,
        resume_from: Optional[str] = None,
    ):
        """
        Run the EUR-Lex ETL pipeline with checkpointing.

        Args:
            limit: Maximum number of EUR-Lex documents to process
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
                logger.info(f"Starting new EUR-Lex pipeline run: {run_id}")

            # Step 1: Initialize Qdrant collection
            if self.state["vectors_uploaded"] == 0:
                logger.info("\n=== Step 1: Initialize Qdrant Collection ===")
                self.qdrant_client.create_collection(
                    vector_size=self.embedder.embedding_dim,
                    force=force_recreate_collection
                )
                self._save_checkpoint()

            # Step 2: Fetch EUR-Lex data (or load from checkpoint)
            if self.state["documents_fetched"] == 0:
                logger.info("\n=== Step 2: Load EUR-Lex Documents ===")
                logger.info(f"Loading up to {limit} EUR-Lex documents...")

                # Load EUR-Lex documents
                eurlex_docs = self.eurlex_loader.load_documents(limit=limit)
                logger.info(f"Loaded {len(eurlex_docs)} EUR-Lex documents")

                # Convert to standard format
                self.all_documents = self._convert_eurlex_to_standard_format(eurlex_docs)
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

            # Step 3: Normalize text (or load from checkpoint)
            if self.state["chunks_created"] == 0 or not self.normalized_docs:
                logger.info("\n=== Step 3: Normalize Text ===")
                self.normalized_docs = self.normalizer.normalize_documents(self.all_documents)

                if not self.normalized_docs:
                    logger.error("Normalization produced no valid documents. Aborting.")
                    self.state["status"] = "failed"
                    self._save_checkpoint()
                    return

                # Save normalized documents
                self.checkpoint_manager.save_normalized(
                    self.state["run_id"],
                    self.normalized_docs
                )
                self._save_checkpoint()
            else:
                # Resume: load normalized docs
                logger.info(f"\n=== Step 3: Loading normalized documents from checkpoint ===")
                self.normalized_docs = self.checkpoint_manager.load_normalized(self.state["run_id"])

            # Step 4: Chunk documents in batches (or skip if already done)
            if self.state["chunks_created"] == 0:
                logger.info("\n=== Step 4: Chunk Documents (Batched Processing) ===")

                CHUNK_BATCH_SIZE = 1000  # Process 1000 docs at a time
                total_chunks = 0

                # Use batched chunking generator (memory-efficient)
                for chunk_batch in self.chunker.chunk_documents_batched(
                    self.normalized_docs,
                    batch_size=CHUNK_BATCH_SIZE
                ):
                    # Save batch incrementally to disk
                    self.checkpoint_manager.append_chunks(self.state['run_id'], chunk_batch)

                    # Update state after each batch
                    total_chunks += len(chunk_batch)
                    self.state['chunks_created'] = total_chunks
                    self._save_checkpoint()

                    logger.info(f"✓ Saved batch to disk: {total_chunks} total chunks created so far")

                if total_chunks == 0:
                    logger.error("Chunking produced no chunks. Aborting.")
                    self.state["status"] = "failed"
                    self._save_checkpoint()
                    return

                logger.info(f"✓ Chunking complete: {total_chunks} chunks saved to disk")

            # Step 5: Generate embeddings and upload in batches
            if self.state["vectors_uploaded"] == 0:
                logger.info("\n=== Step 5: Generate Embeddings & Upload (Batched Processing) ===")

                EMBEDDING_BATCH_SIZE = 1000  # Process 1000 chunks at a time
                total_chunks = self.state["chunks_created"]
                total_vectors_uploaded = 0

                logger.info(f"Processing {total_chunks} chunks in batches of {EMBEDDING_BATCH_SIZE}")

                # Load and process chunks in batches (streaming from disk)
                chunks_path = self.checkpoint_manager._get_chunks_path(self.state["run_id"])

                with open(chunks_path, "r", encoding="utf-8") as f:
                    chunk_batch = []

                    for line in f:
                        if line.strip():
                            chunk_batch.append(json.loads(line))

                            # Process batch when full
                            if len(chunk_batch) >= EMBEDDING_BATCH_SIZE:
                                # Generate embeddings for this batch on GPU via Modal (31x speedup)
                                embed_func = modal.Function.from_name("juragpt-embedder", "embed_batch_gpu")
                                texts = [chunk["text"] for chunk in chunk_batch]
                                batch_embeddings = embed_func.remote(texts)

                                # Add unique IDs (hash-based for stability)
                                for chunk in chunk_batch:
                                    chunk_id_str = chunk.get("chunk_id", str(chunk))
                                    chunk_hash = int(hashlib.md5(chunk_id_str.encode()).hexdigest()[:16], 16)
                                    chunk["id"] = chunk_hash

                                # Upsert batch to Qdrant
                                self.qdrant_client.upsert_chunks(chunk_batch, batch_embeddings)

                                # Update progress
                                total_vectors_uploaded += len(batch_embeddings)
                                self.state["vectors_uploaded"] = total_vectors_uploaded
                                self._save_checkpoint()

                                logger.info(
                                    f"✓ Uploaded batch: {total_vectors_uploaded}/{total_chunks} vectors "
                                    f"({100*total_vectors_uploaded/total_chunks:.1f}%)"
                                )

                                # Clear batch
                                chunk_batch = []

                    # Process remaining chunks
                    if chunk_batch:
                        # Generate embeddings for final batch on GPU via Modal (31x speedup)
                        embed_func = modal.Function.from_name("juragpt-embedder", "embed_batch_gpu")
                        texts = [chunk["text"] for chunk in chunk_batch]
                        batch_embeddings = embed_func.remote(texts)

                        for chunk in chunk_batch:
                            chunk_id_str = chunk.get("chunk_id", str(chunk))
                            chunk_hash = int(hashlib.md5(chunk_id_str.encode()).hexdigest()[:16], 16)
                            chunk["id"] = chunk_hash

                        self.qdrant_client.upsert_chunks(chunk_batch, batch_embeddings)

                        total_vectors_uploaded += len(batch_embeddings)
                        self.state["vectors_uploaded"] = total_vectors_uploaded
                        self._save_checkpoint()

                        logger.info(f"✓ Uploaded final batch: {total_vectors_uploaded}/{total_chunks} vectors")

                # Mark as completed
                self.state["status"] = "completed"
                self._save_checkpoint()

                logger.info(f"✓ Successfully uploaded {total_vectors_uploaded} vectors to Qdrant")

            # Step 7: Verify
            logger.info("\n=== Step 7: Verify Collection ===")
            collection_info = self.qdrant_client.get_collection_info()
            logger.info(f"Collection: {collection_info['name']}")
            logger.info(f"Total points in collection: {collection_info['points_count']}")

            # Final summary
            elapsed_time = time.time() - start_time
            logger.info("\n" + "=" * 70)
            logger.info("EUR-LEX INGESTION COMPLETE")
            logger.info("=" * 70)
            logger.info(f"Run ID: {self.state['run_id']}")
            logger.info(f"Documents processed: {self.state['documents_fetched']}")
            logger.info(f"Chunks created: {self.state['chunks_created']}")
            logger.info(f"Vectors uploaded: {self.state['vectors_uploaded']}")
            logger.info(f"Total time: {elapsed_time:.1f} seconds ({elapsed_time/60:.1f} minutes)")
            logger.info(f"Status: {self.state['status']}")

        except KeyboardInterrupt:
            logger.warning("\n\nPipeline interrupted by user (Ctrl+C)")
            logger.info("Progress saved to checkpoint. Resume with:")
            logger.info(f"  python scripts/ingest_eurlex.py --resume {self.state['run_id']}")
            self.state["status"] = "interrupted"
            self._save_checkpoint()
            raise

        except Exception as e:
            logger.error(f"Pipeline failed with error: {e}", exc_info=True)
            self.state["status"] = "failed"
            self._save_checkpoint()
            raise


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="EUR-Lex ETL Pipeline with Checkpointing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test with 1000 documents
  python scripts/ingest_eurlex.py --limit 1000

  # Full dataset (57,000 documents)
  python scripts/ingest_eurlex.py --limit 57000

  # Resume from checkpoint
  python scripts/ingest_eurlex.py --resume 2025-10-29T15-00-00

  # List all checkpoints
  python scripts/ingest_eurlex.py --list-checkpoints

  # Delete old checkpoint
  python scripts/ingest_eurlex.py --delete-checkpoint 2025-10-29T15-00-00
        """
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=1000,
        help="Maximum number of EUR-Lex documents to process (default: 1000, max: 57000)"
    )
    parser.add_argument(
        "--force-recreate-collection",
        action="store_true",
        help="Force recreate Qdrant collection (WARNING: deletes existing data)"
    )
    parser.add_argument(
        "--resume",
        type=str,
        help="Resume from checkpoint with given run_id"
    )
    parser.add_argument(
        "--list-checkpoints",
        action="store_true",
        help="List all available EUR-Lex checkpoints"
    )
    parser.add_argument(
        "--delete-checkpoint",
        type=str,
        help="Delete checkpoint with given run_id"
    )

    args = parser.parse_args()

    # Create checkpoint manager for listing/deleting
    checkpoint_manager = CheckpointManager(checkpoint_dir=Path("data/checkpoints_eurlex"))

    # List checkpoints
    if args.list_checkpoints:
        checkpoint_manager.list_checkpoints()
        return

    # Delete checkpoint
    if args.delete_checkpoint:
        checkpoint_manager.delete_checkpoint(args.delete_checkpoint)
        return

    # Run pipeline
    pipeline = EURLexPipeline()

    try:
        pipeline.run(
            limit=args.limit,
            force_recreate_collection=args.force_recreate_collection,
            resume_from=args.resume,
        )
    except KeyboardInterrupt:
        logger.info("\nGracefully shutting down...")
        sys.exit(130)  # Standard exit code for Ctrl+C
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
