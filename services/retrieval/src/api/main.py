"""
ABOUTME: FastAPI service for legal document retrieval.
ABOUTME: Provides REST API endpoint for semantic search over the legal corpus.
"""

import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import logging

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.storage.qdrant_client import JuraGPTQdrantClient
from src.embedding.embedder import LegalTextEmbedder

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="JuraGPT Retrieval API",
    description="Semantic search over German & EU legal texts",
    version="1.0.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure based on deployment
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize components (lazy loading)
qdrant_client: Optional[JuraGPTQdrantClient] = None
embedder: Optional[LegalTextEmbedder] = None


def get_qdrant_client() -> JuraGPTQdrantClient:
    """Get or initialize Qdrant client."""
    global qdrant_client
    if qdrant_client is None:
        logger.info("Initializing Qdrant client...")
        qdrant_client = JuraGPTQdrantClient()
    return qdrant_client


def get_embedder() -> LegalTextEmbedder:
    """Get or initialize embedder."""
    global embedder
    if embedder is None:
        logger.info("Initializing embedder...")
        embedder = LegalTextEmbedder()
    return embedder


# Request/Response models
class RetrievalRequest(BaseModel):
    """Request model for retrieval endpoint."""

    query: str = Field(..., description="Search query text", min_length=1)
    top_k: int = Field(5, description="Number of results to return", ge=1, le=50)
    filters: Optional[Dict[str, Any]] = Field(
        None,
        description="Optional filters (e.g., {'type': 'statute', 'law': 'BGB'})",
    )


class RetrievalResult(BaseModel):
    """Single retrieval result."""

    text: str = Field(..., description="Document text")
    title: Optional[str] = Field(None, description="Document title")
    source: Optional[str] = Field(None, description="Source (law or court name)")
    url: Optional[str] = Field(None, description="Source URL")
    score: float = Field(..., description="Relevance score")
    metadata: Dict[str, Any] = Field(..., description="Document metadata")


class RetrievalResponse(BaseModel):
    """Response model for retrieval endpoint."""

    query: str = Field(..., description="Original query")
    results: List[RetrievalResult] = Field(..., description="Search results")
    total_results: int = Field(..., description="Number of results returned")


class CollectionInfo(BaseModel):
    """Collection information."""

    name: str
    points_count: int
    vectors_count: int
    status: str


# Endpoints
@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "JuraGPT Retrieval API",
        "version": "1.0.0",
        "endpoints": {
            "retrieve": "/api/retrieve",
            "health": "/health",
            "info": "/info",
        },
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        # Check Qdrant connection
        client = get_qdrant_client()
        collection_info = client.get_collection_info()

        return {
            "status": "healthy",
            "qdrant_connected": True,
            "collection": collection_info["name"],
            "documents": collection_info["points_count"],
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail=f"Service unhealthy: {str(e)}")


@app.get("/info", response_model=CollectionInfo)
async def get_info():
    """Get collection information."""
    try:
        client = get_qdrant_client()
        info = client.get_collection_info()
        return CollectionInfo(**info)
    except Exception as e:
        logger.error(f"Error getting collection info: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/retrieve", response_model=RetrievalResponse)
async def retrieve(request: RetrievalRequest):
    """
    Retrieve relevant legal documents for a query.

    Args:
        request: Retrieval request with query, top_k, and optional filters

    Returns:
        List of relevant documents with scores
    """
    try:
        logger.info(f"Retrieval request: query='{request.query}', top_k={request.top_k}")

        # Get components
        client = get_qdrant_client()
        emb = get_embedder()

        # Generate query embedding
        query_vector = emb.encode_query(request.query)

        # Search Qdrant
        results = client.search(
            query_vector=query_vector,
            top_k=request.top_k,
            filters=request.filters,
        )

        # Format response
        retrieval_results = [
            RetrievalResult(
                text=r["text"] or "",
                title=r["title"],
                source=r["source"],
                url=r["url"],
                score=r["score"],
                metadata=r["metadata"],
            )
            for r in results
        ]

        response = RetrievalResponse(
            query=request.query,
            results=retrieval_results,
            total_results=len(retrieval_results),
        )

        logger.info(f"Returned {len(retrieval_results)} results")
        return response

    except Exception as e:
        logger.error(f"Retrieval error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/search")
async def search_simple(
    q: str = Query(..., description="Search query"),
    limit: int = Query(5, description="Number of results", ge=1, le=50),
):
    """
    Simple GET endpoint for retrieval (for easy testing).

    Args:
        q: Search query
        limit: Number of results

    Returns:
        Search results
    """
    request = RetrievalRequest(query=q, top_k=limit)
    return await retrieve(request)


# Startup event
@app.on_event("startup")
async def startup_event():
    """Initialize components on startup."""
    logger.info("Starting JuraGPT Retrieval API...")
    try:
        # Pre-load components
        get_qdrant_client()
        get_embedder()
        logger.info("API ready")
    except Exception as e:
        logger.error(f"Startup failed: {e}")
        raise


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
