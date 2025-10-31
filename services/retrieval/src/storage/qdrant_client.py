"""
ABOUTME: Qdrant client for vector storage and retrieval operations.
ABOUTME: Handles collection creation, upserting chunks, and similarity search.
"""

import os
import logging
import hashlib
from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
)
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class JuraGPTQdrantClient:
    """Qdrant client for JuraGPT legal corpus."""

    def __init__(
        self,
        url: Optional[str] = None,
        api_key: Optional[str] = None,
        collection_name: Optional[str] = None,
    ):
        """
        Initialize Qdrant client.

        Args:
            url: Qdrant server URL (defaults to env QDRANT_URL)
            api_key: Qdrant API key (defaults to env QDRANT_API_KEY)
            collection_name: Collection name (defaults to env QDRANT_COLLECTION)
        """
        self.url = url or os.getenv("QDRANT_URL")
        self.api_key = api_key or os.getenv("QDRANT_API_KEY")
        self.collection_name = collection_name or os.getenv(
            "QDRANT_COLLECTION", "juragpt_public_law"
        )

        if not self.url or not self.api_key:
            raise ValueError(
                "Qdrant URL and API key must be provided via parameters or environment variables"
            )

        # Initialize Qdrant client with gRPC for 2-4x speedup
        self.client = QdrantClient(
            url=self.url,
            api_key=self.api_key,
            prefer_grpc=True,  # Use gRPC for bulk uploads (fallback to REST if unavailable)
            timeout=300,  # 5 minute timeout for large batches
            grpc_options={
                'grpc.max_send_message_length': 100 * 1024 * 1024,  # 100MB
                'grpc.max_receive_message_length': 100 * 1024 * 1024,
            }
        )
        logger.info(f"Connected to Qdrant at {self.url} (prefer_grpc=True)")

    def create_collection(
        self, vector_size: int = 1024, distance: Distance = Distance.COSINE, force: bool = False
    ):
        """
        Create Qdrant collection with specified parameters.

        Args:
            vector_size: Dimension of embedding vectors (default: 1024 for multilingual-e5-large)
            distance: Distance metric (default: COSINE)
            force: If True, recreate collection if it exists
        """
        try:
            # Check if collection exists
            collections = self.client.get_collections().collections
            collection_exists = any(c.name == self.collection_name for c in collections)

            if collection_exists:
                if force:
                    logger.warning(f"Deleting existing collection: {self.collection_name}")
                    self.client.delete_collection(self.collection_name)
                else:
                    logger.info(f"Collection {self.collection_name} already exists")
                    return

            # Create collection
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(size=vector_size, distance=distance),
            )
            logger.info(
                f"Created collection {self.collection_name} with vector_size={vector_size}, distance={distance}"
            )

            # Create payload indexes for filtering
            self._create_payload_indexes()

        except Exception as e:
            logger.error(f"Error creating collection: {e}")
            raise

    def _create_payload_indexes(self):
        """Create indexes on payload fields for efficient filtering."""
        index_fields = ["type", "law", "court", "jurisdiction", "date"]

        for field in index_fields:
            try:
                self.client.create_payload_index(
                    collection_name=self.collection_name,
                    field_name=field,
                    field_schema="keyword",
                )
                logger.info(f"Created payload index on field: {field}")
            except Exception as e:
                logger.warning(f"Could not create index on {field}: {e}")

    def upsert_chunks(
        self, chunks: List[Dict[str, Any]], vectors: List[List[float]], batch_size: int = 100
    ):
        """
        Upsert document chunks with embeddings to Qdrant.

        Args:
            chunks: List of chunk dictionaries with metadata
            vectors: Corresponding embedding vectors
            batch_size: Number of points to upload per batch
        """
        if len(chunks) != len(vectors):
            raise ValueError("Number of chunks must match number of vectors")

        total_chunks = len(chunks)
        logger.info(f"Upserting {total_chunks} chunks in batches of {batch_size}")

        # Process in batches
        for i in range(0, total_chunks, batch_size):
            batch_chunks = chunks[i : i + batch_size]
            batch_vectors = vectors[i : i + batch_size]

            # Create points with hash-based IDs to prevent collisions
            points = []
            for idx, (chunk, vector) in enumerate(zip(batch_chunks, batch_vectors)):
                # Generate stable hash-based ID from chunk_id to prevent collisions across pipelines
                chunk_id = chunk.get("id")
                if chunk_id is None:
                    # Use chunk_id field to generate deterministic hash
                    chunk_id_str = chunk.get("chunk_id", f"{i}_{idx}")
                    chunk_id = int(hashlib.md5(chunk_id_str.encode()).hexdigest()[:16], 16)

                points.append(PointStruct(
                    id=chunk_id,
                    vector=vector,
                    payload={
                        "doc_id": chunk.get("doc_id"),
                        "title": chunk.get("title"),
                        "text": chunk.get("text"),
                        "url": chunk.get("url"),
                        "type": chunk.get("type"),  # "statute" | "case" | "regulation"
                        "jurisdiction": chunk.get("jurisdiction", "DE"),
                        "law": chunk.get("law"),  # e.g., "BGB", "StGB"
                        "court": chunk.get("court"),  # e.g., "BGH", "BVerfG"
                        "section": chunk.get("section"),  # e.g., "§823"
                        "date": chunk.get("date"),
                        "case_id": chunk.get("case_id"),  # For court cases
                    },
                ))


            # Upsert to Qdrant
            try:
                self.client.upsert(collection_name=self.collection_name, points=points)
                logger.info(f"Uploaded batch {i // batch_size + 1}/{(total_chunks + batch_size - 1) // batch_size}")
            except Exception as e:
                logger.error(f"Error uploading batch {i // batch_size + 1}: {e}")
                raise

        logger.info(f"Successfully upserted {total_chunks} chunks")

    def search(
        self,
        query_vector: List[float],
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search for similar documents.

        Args:
            query_vector: Query embedding vector
            top_k: Number of results to return
            filters: Optional filters (e.g., {"type": "statute", "law": "BGB"})

        Returns:
            List of search results with scores and metadata
        """
        # Build Qdrant filter if provided
        qdrant_filter = None
        if filters:
            conditions = []
            for key, value in filters.items():
                conditions.append(FieldCondition(key=key, match=MatchValue(value=value)))

            if conditions:
                qdrant_filter = Filter(must=conditions)

        # Perform search
        try:
            results = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                limit=top_k,
                query_filter=qdrant_filter,
            )

            # Format results
            formatted_results = []
            for result in results:
                formatted_results.append(
                    {
                        "text": result.payload.get("text"),
                        "title": result.payload.get("title"),
                        "source": result.payload.get("law") or result.payload.get("court"),
                        "url": result.payload.get("url"),
                        "score": result.score,
                        "metadata": {
                            "type": result.payload.get("type"),
                            "jurisdiction": result.payload.get("jurisdiction"),
                            "law": result.payload.get("law"),
                            "court": result.payload.get("court"),
                            "section": result.payload.get("section"),
                            "date": result.payload.get("date"),
                            "case_id": result.payload.get("case_id"),
                        },
                    }
                )

            logger.info(f"Found {len(formatted_results)} results")
            return formatted_results

        except Exception as e:
            logger.error(f"Error searching: {e}")
            raise

    def get_collection_info(self) -> Dict[str, Any]:
        """Get information about the collection."""
        try:
            collection_info = self.client.get_collection(self.collection_name)
            return {
                "name": self.collection_name,
                "vectors_count": collection_info.vectors_count,
                "points_count": collection_info.points_count,
                "status": collection_info.status,
            }
        except Exception as e:
            logger.error(f"Error getting collection info: {e}")
            raise

    def delete_collection(self):
        """Delete the collection."""
        try:
            self.client.delete_collection(self.collection_name)
            logger.info(f"Deleted collection: {self.collection_name}")
        except Exception as e:
            logger.error(f"Error deleting collection: {e}")
            raise
