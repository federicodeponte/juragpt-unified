#!/usr/bin/env python3
"""
ABOUTME: Incremental corpus update script for JuraGPT with GPU acceleration
ABOUTME: Fetches only new documents since last update and upserts to Qdrant

Incremental corpus update script for JuraGPT.

Fetches only NEW documents since last update (not entire corpus).
Uses existing checkpointing if interrupted, but designed for quick runs.

Key features:
- Fetches documents with created_date__gte=<last_update>
- Skips work if no new documents
- Uses Modal GPU for 31x faster embeddings
- Upserts to existing Qdrant collection (no recreation)
- Tracks update timestamp on success
- Can be run daily via cron

Usage:
    # Update corpus with new documents
    python scripts/update_corpus.py

    # Preview what would be updated (no changes)
    python scripts/update_corpus.py --dry-run

    # Force full update (ignore last timestamp)
    python scripts/update_corpus.py --full

    # Show stats without updating
    python scripts/update_corpus.py --stats
"""

import sys
import argparse
import logging
import time
import hashlib
import modal
from pathlib import Path
from datetime import datetime
from typing import Optional

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.crawlers.openlegaldata_api import OpenLegalDataAPI
from src.processing.normalizer import TextNormalizer
from src.processing.chunker import TextChunker
from src.embedding.embedder import LegalTextEmbedder
from src.storage.qdrant_client import JuraGPTQdrantClient
from src.state.update_tracker import UpdateTracker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class IncrementalUpdateService:
    """
    Handles incremental corpus updates.

    Fetches only new documents since last update to avoid
    re-processing the entire corpus.
    """

    def __init__(self):
        """Initialize update service components."""
        logger.info("Initializing incremental update service...")

        self.api_client = OpenLegalDataAPI()
        self.normalizer = TextNormalizer()
        self.chunker = TextChunker()
        self.embedder = LegalTextEmbedder()
        self.qdrant_client = JuraGPTQdrantClient()
        self.update_tracker = UpdateTracker()

        logger.info("Update service initialized")

    def run_update(
        self,
        force_full: bool = False,
        dry_run: bool = False,
        max_laws: Optional[int] = None,
        max_cases: Optional[int] = None,
    ) -> dict:
        """
        Run incremental update.

        Args:
            force_full: Ignore last update timestamp (fetch all)
            dry_run: Preview changes without updating database
            max_laws: Maximum laws to fetch (None = all new)
            max_cases: Maximum cases to fetch (None = all new)

        Returns:
            Dictionary with update results
        """
        start_time = time.time()

        logger.info("\n" + "=" * 70)
        logger.info("INCREMENTAL CORPUS UPDATE")
        logger.info("=" * 70)

        # Step 1: Get last update timestamp
        if force_full:
            logger.info("\nForce full update (ignoring last timestamp)")
            since_date = None
        else:
            since_date = self.update_tracker.get_last_update_iso()
            if since_date:
                logger.info(f"\nFetching documents since: {since_date}")
            else:
                logger.info("\nNo previous update found - fetching all documents")

        # Step 2: Fetch new documents
        logger.info("\n=== Step 1: Fetch New Documents ===")
        all_documents = []

        logger.info("Fetching new laws...")
        laws_docs = self.api_client.fetch_laws(
            limit=max_laws,
            max_pages=100,  # More pages for incremental updates
            created_date_gte=since_date
        )
        all_documents.extend(laws_docs)
        logger.info(f"Fetched {len(laws_docs)} new laws")

        logger.info("Fetching new cases...")
        cases_docs = self.api_client.fetch_cases(
            limit=max_cases,
            max_pages=100,
            created_date_gte=since_date
        )
        all_documents.extend(cases_docs)
        logger.info(f"Fetched {len(cases_docs)} new cases")

        # Early exit if no new documents
        if not all_documents:
            logger.info("\n✓ No new documents found - corpus is up to date!")
            elapsed = time.time() - start_time
            return {
                "success": True,
                "documents_processed": 0,
                "chunks_created": 0,
                "vectors_uploaded": 0,
                "elapsed_time": elapsed,
                "message": "No new documents"
            }

        logger.info(f"\nTotal new documents: {len(all_documents)}")

        # Dry run - stop before processing
        if dry_run:
            logger.info("\n" + "=" * 70)
            logger.info("DRY RUN - NO CHANGES MADE")
            logger.info("=" * 70)
            logger.info(f"Would process {len(all_documents)} new documents")
            logger.info(f"  - Laws: {len(laws_docs)}")
            logger.info(f"  - Cases: {len(cases_docs)}")
            logger.info("\nRun without --dry-run to apply these changes")
            return {
                "success": True,
                "documents_processed": 0,
                "chunks_created": 0,
                "vectors_uploaded": 0,
                "elapsed_time": time.time() - start_time,
                "message": "Dry run - no changes made"
            }

        # Step 3: Normalize
        logger.info("\n=== Step 2: Normalize Text ===")
        normalized_docs = self.normalizer.normalize_documents(all_documents)
        logger.info(f"Normalized {len(normalized_docs)} documents")

        # Step 4: Chunk
        logger.info("\n=== Step 3: Chunk Documents ===")
        chunks = self.chunker.chunk_documents(normalized_docs)
        logger.info(f"Created {len(chunks)} chunks")

        # Step 5: Generate embeddings on GPU via Modal (31x faster than CPU)
        logger.info("\n=== Step 4: Generate Embeddings (Modal GPU) ===")
        embed_func = modal.Function.from_name("juragpt-embedder", "embed_batch_gpu")
        texts = [chunk["text"] for chunk in chunks]
        embeddings = embed_func.remote(texts)
        logger.info(f"Generated {len(embeddings)} embeddings using GPU")

        # Step 6: Upsert to Qdrant (don't recreate collection!)
        logger.info("\n=== Step 5: Upsert to Qdrant ===")

        # Add unique IDs to chunks (use hash of chunk_id to avoid collisions)
        for chunk in chunks:
            # Generate stable numeric ID from chunk_id string
            chunk_id_str = chunk.get("chunk_id", str(chunk))
            chunk_hash = int(hashlib.md5(chunk_id_str.encode()).hexdigest()[:16], 16)
            chunk["id"] = chunk_hash

        self.qdrant_client.upsert_chunks(chunks, embeddings)
        logger.info(f"Upserted {len(embeddings)} vectors")

        # Step 7: Verify
        logger.info("\n=== Step 6: Verify ===")
        collection_info = self.qdrant_client.get_collection_info()
        logger.info(f"Collection: {collection_info['name']}")
        logger.info(f"Total points: {collection_info['points_count']}")

        # Step 8: Save update timestamp on success
        logger.info("\n=== Step 7: Save Update State ===")
        self.update_tracker.save_update(
            timestamp=datetime.now(),
            docs_count=len(all_documents)
        )

        # Summary
        elapsed_time = time.time() - start_time
        logger.info("\n" + "=" * 70)
        logger.info("UPDATE COMPLETE")
        logger.info("=" * 70)
        logger.info(f"Documents processed: {len(all_documents)}")
        logger.info(f"Chunks created: {len(chunks)}")
        logger.info(f"Vectors upserted: {len(embeddings)}")
        logger.info(f"Total time: {elapsed_time:.1f} seconds")
        logger.info(f"Total vectors in collection: {collection_info['points_count']}")

        return {
            "success": True,
            "documents_processed": len(all_documents),
            "chunks_created": len(chunks),
            "vectors_uploaded": len(embeddings),
            "elapsed_time": elapsed_time,
            "total_vectors": collection_info['points_count']
        }

    def show_stats(self):
        """Display update statistics."""
        stats = self.update_tracker.get_stats()

        print("\n" + "=" * 70)
        print("INCREMENTAL UPDATE STATISTICS")
        print("=" * 70)

        if stats["last_update"]:
            print(f"\nLast update: {stats['last_update']}")
            print(f"Documents in last update: {stats['last_update_docs_count']}")
            print(f"Total update runs: {stats['total_runs']}")
        else:
            print("\nNo updates have been run yet.")
            print("Run 'python scripts/update_corpus.py' to start.")

        # Get Qdrant stats
        try:
            collection_info = self.qdrant_client.get_collection_info()
            print(f"\nQdrant collection: {collection_info['name']}")
            print(f"Total vectors: {collection_info['points_count']}")
        except Exception as e:
            logger.error(f"Error getting Qdrant stats: {e}")

        print("=" * 70 + "\n")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Incremental corpus update for JuraGPT",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Update corpus with new documents
  python scripts/update_corpus.py

  # Force full update (ignore last timestamp)
  python scripts/update_corpus.py --full

  # Show statistics
  python scripts/update_corpus.py --stats

  # Limit documents per update
  python scripts/update_corpus.py --max-laws 1000 --max-cases 1000
        """
    )

    parser.add_argument(
        "--full",
        action="store_true",
        help="Force full update (ignore last timestamp)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without updating database"
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show update statistics and exit"
    )
    parser.add_argument(
        "--max-laws",
        type=int,
        help="Maximum number of laws to fetch"
    )
    parser.add_argument(
        "--max-cases",
        type=int,
        help="Maximum number of cases to fetch"
    )

    args = parser.parse_args()

    # Show stats and exit
    if args.stats:
        service = IncrementalUpdateService()
        service.show_stats()
        return

    # Run update
    try:
        service = IncrementalUpdateService()
        result = service.run_update(
            force_full=args.full,
            dry_run=args.dry_run,
            max_laws=args.max_laws,
            max_cases=args.max_cases
        )

        if result["success"]:
            sys.exit(0)
        else:
            sys.exit(1)

    except KeyboardInterrupt:
        logger.info("\nUpdate interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Update failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
