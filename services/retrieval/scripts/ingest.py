#!/usr/bin/env python3
"""
ETL pipeline for JuraGPT legal corpus with checkpointing support.

Pipeline stages:
1. Crawl data from sources (laws, cases)
2. Normalize text
3. Chunk documents
4. Generate embeddings
5. Upsert to Qdrant

Features:
- Resumable pipeline with automatic checkpointing
- Atomic state saves after each major step
- Resume from failed runs using --resume <run_id>

Usage:
    # New run
    python scripts/ingest.py [--laws-only] [--cases-only] [--max-laws 5] [--max-cases 20]

    # Resume failed run
    python scripts/ingest.py --resume 2025-10-28T22-30-00

    # List all checkpoints
    python scripts/ingest.py --list-checkpoints
"""

import sys
import os
import argparse
import logging
import time
from pathlib import Path
from datetime import datetime
from typing import Optional

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.crawlers.openlegaldata_api import OpenLegalDataAPI
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


class ETLPipeline:
    """Orchestrates the full ETL pipeline with checkpointing support."""

    def __init__(self, checkpoint_dir: Path = Path("data/checkpoints")):
        """
        Initialize pipeline components.

        Args:
            checkpoint_dir: Directory for checkpoint files
        """
        logger.info("Initializing ETL pipeline with checkpointing...")

        self.api_client = OpenLegalDataAPI()
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

        logger.info("Pipeline components initialized")

    def run(
        self,
        crawl_laws: bool = True,
        crawl_cases: bool = True,
        crawl_eurlex: bool = False,
        max_laws: int = 2,
        max_cases: int = 20,
        max_eurlex: int = 1000,
        force_recreate_collection: bool = False,
        resume_from: Optional[str] = None,
    ):
        """
        Run the full ETL pipeline with checkpointing.

        Args:
            crawl_laws: Whether to fetch laws from OpenLegalData
            crawl_cases: Whether to fetch cases from OpenLegalData
            crawl_eurlex: Whether to fetch EUR-Lex documents
            max_laws: Maximum number of laws to fetch
            max_cases: Maximum number of cases to fetch
            max_eurlex: Maximum number of EUR-Lex documents to fetch
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
                logger.info(f"Starting new pipeline run: {run_id}")

            # Step 1: Initialize Qdrant collection
            if self.state["vectors_uploaded"] == 0:
                logger.info("\n=== Step 1: Initialize Qdrant Collection ===")
                self.qdrant_client.create_collection(
                    vector_size=self.embedder.embedding_dim,
                    force=force_recreate_collection
                )
                self._save_checkpoint()

            # Step 2: Fetch data (or load from checkpoint)
            if self.state["documents_fetched"] == 0:
                logger.info("\n=== Step 2: Fetch Data from Sources ===")
                self.all_documents = []

                if crawl_laws:
                    logger.info(f"Fetching up to {max_laws} laws...")
                    laws_docs = self.api_client.fetch_laws(limit=max_laws, max_pages=5)
                    self.all_documents.extend(laws_docs)
                    logger.info(f"Fetched {len(laws_docs)} laws")

                if crawl_cases:
                    logger.info(f"Fetching up to {max_cases} cases...")
                    cases_docs = self.api_client.fetch_cases(limit=max_cases, max_pages=5)
                    self.all_documents.extend(cases_docs)
                    logger.info(f"Fetched {len(cases_docs)} court cases")

                if crawl_eurlex:
                    logger.info(f"Fetching up to {max_eurlex} EUR-Lex documents...")
                    self.eurlex_loader.download_dataset()
                    self.eurlex_loader.extract_dataset()
                    eurlex_docs = self.eurlex_loader.load_documents(limit=max_eurlex)
                    self.all_documents.extend(eurlex_docs)
                    logger.info(f"Fetched {len(eurlex_docs)} EUR-Lex documents")

                if not self.all_documents:
                    logger.error("No documents fetched. Aborting pipeline.")
                    self.state["status"] = "failed"
                    self.state["last_error"] = "No documents fetched"
                    self._save_checkpoint()
                    return

                # Save documents to disk
                self.checkpoint_manager.save_documents(self.state["run_id"], self.all_documents)
                self.state["documents_fetched"] = len(self.all_documents)
                logger.info(f"Total documents fetched: {len(self.all_documents)}")
                self._save_checkpoint()
            else:
                logger.info(
                    f"\n=== Step 2: Resuming - Loading {self.state['documents_fetched']} documents from checkpoint ==="
                )
                self.all_documents = self.checkpoint_manager.load_documents(self.state["run_id"])
                if not self.all_documents:
                    logger.error("Failed to load documents from checkpoint!")
                    self.state["status"] = "failed"
                    self.state["last_error"] = "Failed to load documents from checkpoint"
                    self._save_checkpoint()
                    return

            # Step 3: Normalize text (or load from checkpoint)
            if self.state["documents_normalized"] == 0:
                logger.info("\n=== Step 3: Normalize Text ===")
                self.normalized_docs = self.normalizer.normalize_documents(self.all_documents)

                # Save normalized documents to disk
                self.checkpoint_manager.save_normalized(self.state["run_id"], self.normalized_docs)
                self.state["documents_normalized"] = len(self.normalized_docs)
                logger.info(f"Normalized {len(self.normalized_docs)} documents")
                self._save_checkpoint()
            else:
                logger.info(
                    f"\n=== Step 3: Resuming - Loading {self.state['documents_normalized']} normalized documents ==="
                )
                self.normalized_docs = self.checkpoint_manager.load_normalized(self.state["run_id"])
                if not self.normalized_docs:
                    logger.error("Failed to load normalized documents from checkpoint!")
                    self.state["status"] = "failed"
                    self.state["last_error"] = "Failed to load normalized documents"
                    self._save_checkpoint()
                    return

            # Step 4: Chunk documents (or load from checkpoint)
            if self.state["chunks_created"] == 0:
                logger.info("\n=== Step 4: Chunk Documents ===")
                self.chunks = self.chunker.chunk_documents(self.normalized_docs)

                # Save chunks to checkpoint directory (also keep old location for compatibility)
                self.chunker.save_chunks(self.chunks)
                self.checkpoint_manager.save_chunks(self.state["run_id"], self.chunks)
                self.state["chunks_created"] = len(self.chunks)
                logger.info(f"Created {len(self.chunks)} chunks")
                self._save_checkpoint()
            else:
                logger.info(
                    f"\n=== Step 4: Resuming - Loading {self.state['chunks_created']} chunks ==="
                )
                self.chunks = self.checkpoint_manager.load_chunks(self.state["run_id"])
                if not self.chunks:
                    logger.error("Failed to load chunks from checkpoint!")
                    self.state["status"] = "failed"
                    self.state["last_error"] = "Failed to load chunks"
                    self._save_checkpoint()
                    return

            # Step 5: Generate embeddings (skip if already embedded)
            if self.state["vectors_uploaded"] == 0:
                logger.info("\n=== Step 5: Generate Embeddings ===")
                self.embeddings = self.embedder.encode_chunks(self.chunks)
                logger.info(f"Generated {len(self.embeddings)} embeddings")
                self._save_checkpoint()

            # Step 6: Upsert to Qdrant (skip if already uploaded)
            if self.state["vectors_uploaded"] == 0:
                logger.info("\n=== Step 6: Upsert to Qdrant ===")

                # Add unique IDs to chunks
                for i, chunk in enumerate(self.chunks):
                    chunk["id"] = i

                self.qdrant_client.upsert_chunks(self.chunks, self.embeddings)
                self.state["vectors_uploaded"] = len(self.embeddings)
                self._save_checkpoint()

            # Step 7: Verify and mark complete
            logger.info("\n=== Step 7: Verify Ingestion ===")
            collection_info = self.qdrant_client.get_collection_info()
            logger.info(f"Collection: {collection_info['name']}")
            logger.info(f"Points count: {collection_info['points_count']}")
            logger.info(f"Vectors count: {collection_info['vectors_count']}")

            # Mark pipeline as completed
            self.state["status"] = "completed"
            self._save_checkpoint()

            # Pipeline complete
            elapsed_time = time.time() - start_time
            logger.info(f"\n=== Pipeline Complete ===")
            logger.info(f"Run ID: {self.state['run_id']}")
            logger.info(f"Total time: {elapsed_time:.1f} seconds")
            logger.info(f"Documents fetched: {self.state['documents_fetched']}")
            logger.info(f"Documents normalized: {self.state['documents_normalized']}")
            logger.info(f"Chunks created: {self.state['chunks_created']}")
            logger.info(f"Vectors uploaded: {self.state['vectors_uploaded']}")

        except Exception as e:
            logger.error(f"Pipeline failed: {e}", exc_info=True)

            # Save error state
            if self.state:
                self.state["status"] = "failed"
                self.state["error_count"] += 1
                self.state["last_error"] = str(e)
                self._save_checkpoint()
                logger.info(f"Checkpoint saved with failed status. Resume with: --resume {self.state['run_id']}")

            raise

    def _save_checkpoint(self):
        """Save current state to checkpoint."""
        if self.state:
            self.checkpoint_manager.save_checkpoint(self.state)



def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="JuraGPT ETL Pipeline with Checkpointing Support",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # New run with 100 laws and 50 cases
  python scripts/ingest.py --max-laws 100 --max-cases 50

  # Resume a failed run
  python scripts/ingest.py --resume 2025-10-28T22-30-00

  # List all checkpoints
  python scripts/ingest.py --list-checkpoints

  # Delete a checkpoint
  python scripts/ingest.py --delete-checkpoint 2025-10-28T22-30-00
        """
    )

    # Checkpoint management
    parser.add_argument(
        "--resume",
        type=str,
        metavar="RUN_ID",
        help="Resume from checkpoint (provide run_id like '2025-10-28T22-30-00')"
    )
    parser.add_argument(
        "--list-checkpoints",
        action="store_true",
        help="List all available checkpoints and exit"
    )
    parser.add_argument(
        "--delete-checkpoint",
        type=str,
        metavar="RUN_ID",
        help="Delete a specific checkpoint and exit"
    )

    # Data source selection
    parser.add_argument(
        "--laws-only",
        action="store_true",
        help="Only crawl laws (skip cases)"
    )
    parser.add_argument(
        "--cases-only",
        action="store_true",
        help="Only crawl cases (skip laws)"
    )
    parser.add_argument(
        "--max-laws",
        type=int,
        default=10,
        help="Maximum number of laws to fetch (default: 10)"
    )
    parser.add_argument(
        "--max-cases",
        type=int,
        default=20,
        help="Maximum number of cases to fetch (default: 20)"
    )
    parser.add_argument(
        "--eurlex",
        action="store_true",
        help="Fetch EUR-Lex EU legal documents (English)"
    )
    parser.add_argument(
        "--max-eurlex",
        type=int,
        default=1000,
        help="Maximum number of EUR-Lex documents to fetch (default: 1000)"
    )
    parser.add_argument(
        "--force-recreate",
        action="store_true",
        help="Force recreate Qdrant collection"
    )

    args = parser.parse_args()

    # Handle checkpoint management commands
    checkpoint_manager = CheckpointManager()

    if args.list_checkpoints:
        checkpoints = checkpoint_manager.list_checkpoints()
        if not checkpoints:
            print("No checkpoints found.")
            return

        print("\n=== Available Checkpoints ===")
        print(f"{'Run ID':<25} {'Status':<12} {'Docs':<8} {'Chunks':<8} {'Vectors':<8} {'Last Updated'}")
        print("-" * 90)
        for cp in checkpoints:
            print(
                f"{cp['run_id']:<25} {cp['status']:<12} "
                f"{cp['documents_fetched']:<8} {cp['chunks_created']:<8} "
                f"{cp['vectors_uploaded']:<8} {cp['last_updated']}"
            )
        print(f"\nTotal: {len(checkpoints)} checkpoint(s)")
        print("\nTo resume a run: python scripts/ingest.py --resume <run_id>")
        return

    if args.delete_checkpoint:
        success = checkpoint_manager.delete_checkpoint(args.delete_checkpoint)
        if success:
            print(f"Deleted checkpoint: {args.delete_checkpoint}")
        else:
            print(f"Checkpoint not found: {args.delete_checkpoint}")
        return

    # Determine what to crawl
    crawl_laws = not args.cases_only
    crawl_cases = not args.laws_only

    # Run pipeline
    pipeline = ETLPipeline()
    pipeline.run(
        crawl_laws=crawl_laws,
        crawl_cases=crawl_cases,
        crawl_eurlex=args.eurlex,
        max_laws=args.max_laws,
        max_cases=args.max_cases,
        max_eurlex=args.max_eurlex,
        force_recreate_collection=args.force_recreate,
        resume_from=args.resume,
    )


if __name__ == "__main__":
    main()
