"""
ABOUTME: Supabase client wrapper for database operations
ABOUTME: Provides methods for CRUD operations on documents, chunks, and query logs
"""

import uuid
from typing import Any, Dict, List, Optional

from supabase import Client, create_client

from app.config import settings
from app.db.models import ChunkDB, DocumentDB, QueryLogDB


class SupabaseClient:
    """Wrapper for Supabase database operations"""

    def __init__(self):
        self.client: Client = create_client(
            settings.supabase_url,
            settings.supabase_service_role_key,  # Use service role for backend
        )

    # Document Operations

    async def create_document(
        self,
        user_id: uuid.UUID,
        filename: str,
        doc_hash: str,
        file_size_bytes: int,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DocumentDB:
        """Create a new document record"""
        data = {
            "user_id": str(user_id),
            "filename": filename,
            "doc_hash": doc_hash,
            "file_size_bytes": file_size_bytes,
            "metadata": metadata or {},
            "version": 1,
            "status": "active",
        }

        result = self.client.table("documents").insert(data).execute()
        return DocumentDB(**result.data[0])

    async def get_document(self, document_id: uuid.UUID) -> Optional[DocumentDB]:
        """Get document by ID"""
        result = self.client.table("documents").select("*").eq("id", str(document_id)).execute()
        if result.data:
            return DocumentDB(**result.data[0])
        return None

    async def get_documents_by_user(self, user_id: uuid.UUID) -> List[DocumentDB]:
        """Get all documents for a user"""
        result = self.client.table("documents").select("*").eq("user_id", str(user_id)).execute()
        return [DocumentDB(**doc) for doc in result.data]

    # Chunk Operations

    async def create_chunk(
        self,
        document_id: uuid.UUID,
        section_id: str,
        content: str,
        chunk_type: str,
        position: int,
        embedding: List[float],
        parent_id: Optional[uuid.UUID] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ChunkDB:
        """Create a new chunk with embedding"""
        data = {
            "document_id": str(document_id),
            "section_id": section_id,
            "content": content,
            "chunk_type": chunk_type,
            "position": position,
            "embedding": embedding,
            "parent_id": str(parent_id) if parent_id else None,
            "metadata": metadata or {},
        }

        result = self.client.table("chunks").insert(data).execute()
        return ChunkDB(**result.data[0])

    async def create_chunks_batch(self, chunks: List[Dict[str, Any]]) -> List[ChunkDB]:
        """Batch insert chunks for efficiency"""
        result = self.client.table("chunks").insert(chunks).execute()
        return [ChunkDB(**chunk) for chunk in result.data]

    async def get_chunks_by_document(self, document_id: uuid.UUID) -> List[ChunkDB]:
        """Get all chunks for a document"""
        result = (
            self.client.table("chunks")
            .select("*")
            .eq("document_id", str(document_id))
            .order("position")
            .execute()
        )
        return [ChunkDB(**chunk) for chunk in result.data]

    async def get_chunk_by_id(self, chunk_id: uuid.UUID) -> Optional[ChunkDB]:
        """Get a single chunk by ID"""
        result = self.client.table("chunks").select("*").eq("id", str(chunk_id)).execute()
        if result.data:
            return ChunkDB(**result.data[0])
        return None

    # Vector Search Operations

    async def match_chunks(
        self,
        query_embedding: List[float],
        document_id: uuid.UUID,
        match_threshold: float = 0.7,
        match_count: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Perform vector similarity search using Supabase RPC function
        Returns chunks with similarity scores
        """
        result = self.client.rpc(
            "match_chunks",
            {
                "query_embedding": query_embedding,
                "doc_id": str(document_id),
                "match_threshold": match_threshold,
                "match_count": match_count,
            },
        ).execute()

        return result.data

    async def get_context_chunks(self, chunk_id: uuid.UUID) -> Dict[str, Any]:
        """
        Get chunk with its parent and siblings for hierarchical context
        Returns: {target, parent, siblings}
        """
        result = self.client.rpc("get_context_chunks", {"chunk_id": str(chunk_id)}).execute()

        # Organize results by relation type
        context: Dict[str, Any] = {"target": None, "parent": None, "siblings": []}

        for item in result.data:
            if item["relation"] == "target":
                context["target"] = item
            elif item["relation"] == "parent":
                context["parent"] = item
            elif item["relation"] == "sibling":
                context["siblings"].append(item)

        return context

    async def get_context_chunks_batch(self, chunk_ids: List[uuid.UUID]) -> Dict[uuid.UUID, Dict[str, Any]]:
        """
        Get context (parent + siblings) for multiple chunks in a single query

        Optimizes N+1 query pattern:
        - BEFORE: 1 query per chunk (N+1 total)
        - AFTER: 1 query for all chunks (2 total with match_chunks)

        Args:
            chunk_ids: List of chunk UUIDs to get context for

        Returns:
            Dict mapping chunk_id to {target, parent, siblings}

        Example:
            {
                UUID('123...'): {
                    'target': {...},
                    'parent': {...},
                    'siblings': [...]
                }
            }
        """
        if not chunk_ids:
            return {}

        # Call batch RPC function
        result = self.client.rpc(
            "get_context_chunks_batch",
            {"chunk_ids": [str(cid) for cid in chunk_ids]}
        ).execute()

        # Organize results by chunk_id and relation type
        contexts: Dict[uuid.UUID, Dict[str, Any]] = {}

        for item in result.data:
            chunk_id = uuid.UUID(item["chunk_id"])

            # Initialize context dict for this chunk if not exists
            if chunk_id not in contexts:
                contexts[chunk_id] = {"target": None, "parent": None, "siblings": []}

            # Organize by relation type
            if item["relation"] == "target":
                contexts[chunk_id]["target"] = item
            elif item["relation"] == "parent":
                contexts[chunk_id]["parent"] = item
            elif item["relation"] == "sibling":
                contexts[chunk_id]["siblings"].append(item)

        return contexts

    # Query Log Operations

    async def log_query(
        self,
        document_id: uuid.UUID,
        query_hash: str,
        response_hash: Optional[str] = None,
        latency_ms: Optional[int] = None,
        tokens_used: Optional[int] = None,
        model_version: Optional[str] = None,
        citations_count: Optional[int] = None,
        confidence_score: Optional[float] = None,
        error_message: Optional[str] = None,
    ) -> QueryLogDB:
        """Log a query for audit trail"""
        data = {
            "document_id": str(document_id),
            "query_hash": query_hash,
            "response_hash": response_hash,
            "latency_ms": latency_ms,
            "tokens_used": tokens_used,
            "model_version": model_version,
            "citations_count": citations_count,
            "confidence_score": confidence_score,
            "error_message": error_message,
        }

        result = self.client.table("query_logs").insert(data).execute()
        return QueryLogDB(**result.data[0])

    async def get_query_logs(
        self, document_id: Optional[uuid.UUID] = None, limit: int = 100
    ) -> List[QueryLogDB]:
        """Get query logs, optionally filtered by document"""
        query = (
            self.client.table("query_logs").select("*").order("created_at", desc=True).limit(limit)
        )

        if document_id:
            query = query.eq("document_id", str(document_id))

        result = query.execute()
        return [QueryLogDB(**log) for log in result.data]

    # Utility Methods

    async def document_exists(self, doc_hash: str) -> bool:
        """Check if document already exists by hash"""
        result = self.client.table("documents").select("id").eq("doc_hash", doc_hash).execute()
        return len(result.data) > 0

    async def delete_document(self, document_id: uuid.UUID) -> bool:
        """Soft delete a document (marks as deleted)"""
        result = (
            self.client.table("documents")
            .update({"status": "deleted"})
            .eq("id", str(document_id))
            .execute()
        )
        return len(result.data) > 0


# Global instance
supabase_client = SupabaseClient()
