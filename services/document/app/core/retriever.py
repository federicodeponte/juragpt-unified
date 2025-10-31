"""
ABOUTME: Hierarchical RAG retrieval system using pgvector
ABOUTME: Implements parent/sibling context enrichment for improved legal document understanding
"""

import hashlib
import uuid
from typing import Dict, List, Optional

from sentence_transformers import SentenceTransformer

from app.config import settings
from app.db.models import ChunkDB, RetrievalResult
from app.db.supabase_client import supabase_client
from app.utils.logging import logger
from app.utils.metrics import cache_hits_total, cache_misses_total
from app.utils.redis_client import redis_client


class Embedder:
    """
    Generate embeddings using multilingual sentence transformers
    Optimized for German legal text

    Model Configuration:
    - Production: paraphrase-multilingual-mpnet-base-v2 (768 dims)
    - Database schema: vector(768) in app/db/schemas.sql
    - Tests: all-MiniLM-L6-v2 (384 dims) for performance

    IMPORTANT: If changing the embedding model, update the database schema
    to match the new dimension using: ALTER TABLE chunks ALTER COLUMN embedding TYPE vector(NEW_DIM);
    """

    # Expected dimension for production database schema
    EXPECTED_DIMENSION = 768

    def __init__(self, model_name: Optional[str] = None):
        self.model_name = model_name or settings.embedding_model
        logger.info(f"Loading embedding model: {self.model_name}")
        self.model = SentenceTransformer(self.model_name)
        self.embedding_dim = self.model.get_sentence_embedding_dimension()

        # Validate dimension matches database schema (skip in test environment)
        if settings.environment != "test" and self.embedding_dim != self.EXPECTED_DIMENSION:
            logger.warning(
                f"Embedding dimension mismatch: model={self.embedding_dim}, "
                f"expected={self.EXPECTED_DIMENSION}. "
                f"Database schema may need update!"
            )

    def embed_text(self, text: str) -> List[float]:
        """Generate embedding for single text"""
        embedding = self.model.encode(text, convert_to_numpy=True)
        return embedding.tolist()

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts (more efficient)"""
        embeddings = self.model.encode(texts, convert_to_numpy=True, show_progress_bar=True)
        return [emb.tolist() for emb in embeddings]


class Retriever:
    """
    Hierarchical RAG retrieval system
    Retrieves relevant chunks with parent and sibling context
    """

    def __init__(self, embedder: Optional[Embedder] = None):
        self.embedder = embedder or Embedder()

    async def retrieve(
        self,
        query: str,
        document_id: uuid.UUID,
        top_k: Optional[int] = None,
        match_threshold: float = 0.7,
    ) -> List[RetrievalResult]:
        """
        Retrieve relevant chunks with hierarchical context

        Caching Strategy:
        - Cache key: query_hash + document_id + top_k + match_threshold
        - TTL: 1 hour (configurable via settings.cache_query_results_ttl)
        - Cache hit = skip embedding + vector search + context enrichment

        Args:
            query: User query
            document_id: Document to search in
            top_k: Number of chunks to retrieve
            match_threshold: Minimum similarity score

        Returns:
            List of retrieval results with parent/sibling context
        """
        top_k = top_k or settings.default_top_k

        # Check cache if enabled
        cache_key = None
        if settings.cache_enabled:
            # Generate cache key: hash(query + doc_id + top_k + threshold)
            query_hash = hashlib.sha256(query.encode()).hexdigest()[:16]
            cache_key = f"query:{document_id}:{query_hash}:{top_k}:{match_threshold}"

            cached_result = redis_client.get_cached_result(cache_key)
            if cached_result:
                # Reconstruct RetrievalResult objects from cached data
                results = [
                    RetrievalResult(
                        chunk_id=uuid.UUID(r["chunk_id"]),
                        section_id=r["section_id"],
                        content=r["content"],
                        similarity=r["similarity"],
                        parent_content=r.get("parent_content"),
                        sibling_contents=r.get("sibling_contents", []),
                    )
                    for r in cached_result["results"]
                ]

                # Track cache hit metric
                cache_hits_total.labels(cache_type="query_results").inc()

                logger.info(
                    f"Cache HIT: Retrieved {len(results)} chunks from cache",
                    extra={"document_id": str(document_id), "cache_key": cache_key},
                )
                return results

        # Cache MISS - proceed with retrieval
        cache_misses_total.labels(cache_type="query_results").inc()
        logger.info("Cache MISS: Performing retrieval", extra={"document_id": str(document_id)})

        # 1. Generate query embedding
        query_embedding = self.embedder.embed_text(query)

        # 2. Vector similarity search
        matches = await supabase_client.match_chunks(
            query_embedding=query_embedding,
            document_id=document_id,
            match_threshold=match_threshold,
            match_count=top_k,
        )

        if not matches:
            logger.warning(f"No matches found for query in document {document_id}")
            return []

        # 3. Enrich with hierarchical context (batch retrieval - fixes N+1 query pattern)
        chunk_ids = [uuid.UUID(match["id"]) for match in matches]

        # Single batch query instead of N queries
        contexts = await supabase_client.get_context_chunks_batch(chunk_ids)

        # Build retrieval results
        results = []
        for match in matches:
            chunk_id = uuid.UUID(match["id"])
            context = contexts.get(chunk_id, {"target": None, "parent": None, "siblings": []})

            result = RetrievalResult(
                chunk_id=chunk_id,
                section_id=match["section_id"],
                content=match["content"],
                similarity=match["similarity"],
                parent_content=context["parent"]["content"] if context["parent"] else None,
                sibling_contents=[sib["content"] for sib in context["siblings"]],
            )
            results.append(result)

        logger.info(
            f"Retrieved {len(results)} chunks for query",
            extra={
                "document_id": str(document_id),
                "top_k": top_k,
                "avg_similarity": sum(r.similarity for r in results) / len(results),
            },
        )

        # Cache results if enabled
        if settings.cache_enabled and cache_key and results:
            # Serialize results for caching
            cache_data = {
                "results": [
                    {
                        "chunk_id": str(r.chunk_id),
                        "section_id": r.section_id,
                        "content": r.content,
                        "similarity": r.similarity,
                        "parent_content": r.parent_content,
                        "sibling_contents": r.sibling_contents,
                    }
                    for r in results
                ],
                "metadata": {
                    "document_id": str(document_id),
                    "top_k": top_k,
                    "match_threshold": match_threshold,
                },
            }
            redis_client.cache_query_result(cache_key, cache_data, ttl=settings.cache_query_results_ttl)
            logger.info(
                f"Cached {len(results)} retrieval results",
                extra={"cache_key": cache_key, "ttl": settings.cache_query_results_ttl},
            )

        return results

    def format_context(self, results: List[RetrievalResult]) -> str:
        """
        Format retrieval results into context for LLM

        Includes target chunk + parent + siblings for each result
        """
        formatted_sections = []

        for i, result in enumerate(results, 1):
            section_text = f"### Retrieved Section {i}: {result.section_id}\n\n"

            # Add parent context if available
            if result.parent_content:
                section_text += f"**Parent Context:**\n{result.parent_content}\n\n"

            # Add target chunk
            section_text += f"**Target Content:**\n{result.content}\n\n"

            # Add sibling context if available
            if result.sibling_contents:
                section_text += "**Related Sections:**\n"
                for j, sibling in enumerate(result.sibling_contents[:3], 1):  # Limit to 3 siblings
                    section_text += f"{j}. {sibling[:200]}...\n"  # Truncate long siblings

            section_text += f"\n*(Relevance: {result.similarity:.2%})*\n"
            section_text += "-" * 80 + "\n\n"

            formatted_sections.append(section_text)

        return "\n".join(formatted_sections)

    async def index_document_chunks(self, chunks: List[Dict], document_id: uuid.UUID) -> int:
        """
        Generate embeddings and index document chunks

        Args:
            chunks: List of chunk dictionaries from document parser
            document_id: Document UUID

        Returns:
            Number of chunks indexed
        """
        if not chunks:
            return 0

        # 1. Extract texts for embedding
        texts = [chunk["content"] for chunk in chunks]

        # 2. Generate embeddings in batch (more efficient)
        logger.info(f"Generating embeddings for {len(texts)} chunks")
        embeddings = self.embedder.embed_batch(texts)

        # 3. Add embeddings to chunk data
        for chunk, embedding in zip(chunks, embeddings):
            chunk["embedding"] = embedding
            chunk["document_id"] = str(document_id)

        # 4. Batch insert into database
        logger.info(f"Inserting {len(chunks)} chunks into database")
        await supabase_client.create_chunks_batch(chunks)

        logger.info(
            f"Indexed {len(chunks)} chunks for document",
            extra={"document_id": str(document_id), "chunk_count": len(chunks)},
        )

        return len(chunks)

    async def get_chunk_by_section_id(
        self, document_id: uuid.UUID, section_id: str
    ) -> Optional[ChunkDB]:
        """
        Get chunk by section ID (e.g., "§5.2")
        Useful for citation verification
        """
        chunks = await supabase_client.get_chunks_by_document(document_id)

        for chunk in chunks:
            if chunk.section_id == section_id:
                return chunk

        return None


# Lazy initialization pattern - prevents import-time side effects
_retriever_instance: Optional[Retriever] = None


def get_retriever() -> Retriever:
    """
    Get or create the global retriever instance (lazy initialization)

    This pattern prevents import-time side effects and makes testing easier.
    Follows Dependency Inversion Principle (SOLID).
    """
    global _retriever_instance
    if _retriever_instance is None:
        _retriever_instance = Retriever()
    return _retriever_instance


# For backwards compatibility (will be removed in future versions)
# Usage: from app.core.retriever import retriever
# Recommended: Use get_retriever() instead for explicit lazy loading
def __getattr__(name: str):
    """Module-level attribute access for backwards compatibility"""
    if name == "retriever":
        return get_retriever()
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
