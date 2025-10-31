#!/usr/bin/env python3
"""
ABOUTME: Orchestrator API gateway for JuraGPT Unified
ABOUTME: Combines retrieval and verification services into single endpoint
"""

from fastapi import FastAPI, HTTPException, Depends, Header
from pydantic import BaseModel, Field
from typing import List, Optional
import httpx
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="JuraGPT Unified API")

# Service URLs (from environment)
RETRIEVAL_URL = os.getenv("RETRIEVAL_URL", "http://retrieval:8001")
VERIFICATION_URL = os.getenv("VERIFICATION_URL", "http://verification:8002")
ENABLE_AUTH = os.getenv("ENABLE_AUTH", "false").lower() == "true"


class QueryRequest(BaseModel):
    query: str = Field(..., description="Legal question to answer")
    top_k: int = Field(5, description="Number of sources to retrieve")
    answer: Optional[str] = Field(None, description="Pre-generated answer (optional)")
    generate_answer: bool = Field(False, description="Whether to generate answer via LLM")
    verify_answer: bool = Field(True, description="Whether to verify the answer")


class Source(BaseModel):
    doc_id: str
    title: str
    text: str
    score: float


class QueryResponse(BaseModel):
    query: str
    sources: List[Source]
    answer: Optional[str] = None
    verification: Optional[dict] = None


@app.post("/query", response_model=QueryResponse)
async def unified_query(
    request: QueryRequest,
    authorization: Optional[str] = Header(None)
):
    """
    Unified query endpoint: retrieve → generate → verify

    Steps:
    1. Retrieve relevant sources from Qdrant (retrieval service)
    2. Generate answer using LLM (optional, external)
    3. Verify answer against sources (verification service)
    """

    # Step 1: Retrieve sources
    logger.info(f"Retrieving sources for query: {request.query[:50]}...")
    async with httpx.AsyncClient() as client:
        try:
            retrieval_response = await client.post(
                f"{RETRIEVAL_URL}/retrieve",
                json={"query": request.query, "top_k": request.top_k},
                timeout=30.0
            )
            retrieval_response.raise_for_status()
            retrieval_data = retrieval_response.json()
            sources = retrieval_data.get("sources", [])

        except Exception as e:
            logger.error(f"Retrieval failed: {e}")
            raise HTTPException(status_code=500, detail=f"Retrieval failed: {str(e)}")

    # Step 2: Generate answer (placeholder - integrate with LLM later)
    answer = request.answer
    if request.generate_answer and not answer:
        # TODO: Integrate with LLM (GPT-4, Claude, etc.)
        answer = f"[Answer would be generated here based on {len(sources)} sources]"

    # Step 3: Verify answer (if provided)
    verification = None
    if answer and request.verify_answer:
        logger.info("Verifying answer against sources...")
        async with httpx.AsyncClient() as client:
            try:
                verify_response = await client.post(
                    f"{VERIFICATION_URL}/verify",
                    json={
                        "answer": answer,
                        "sources": [s["text"] for s in sources]
                    },
                    timeout=60.0
                )
                verify_response.raise_for_status()
                verification = verify_response.json()

            except Exception as e:
                logger.warning(f"Verification failed: {e}")
                # Continue without verification

    return QueryResponse(
        query=request.query,
        sources=sources,
        answer=answer,
        verification=verification
    )


@app.post("/retrieve")
async def retrieve_only(query: str, top_k: int = 5):
    """Retrieval only (pass-through to retrieval service)."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{RETRIEVAL_URL}/retrieve",
            json={"query": query, "top_k": top_k}
        )
        response.raise_for_status()
        return response.json()


@app.post("/verify")
async def verify_only(answer: str, sources: List[str]):
    """Verification only (pass-through to verification service)."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{VERIFICATION_URL}/verify",
            json={"answer": answer, "sources": sources}
        )
        response.raise_for_status()
        return response.json()


@app.get("/health")
async def health():
    """Health check for all services."""
    health_status = {"status": "healthy", "services": {}}

    async with httpx.AsyncClient() as client:
        # Check retrieval service
        try:
            r = await client.get(f"{RETRIEVAL_URL}/health", timeout=5.0)
            health_status["services"]["retrieval"] = "healthy" if r.status_code == 200 else "unhealthy"
        except:
            health_status["services"]["retrieval"] = "unreachable"

        # Check verification service
        try:
            v = await client.get(f"{VERIFICATION_URL}/health", timeout=5.0)
            health_status["services"]["verification"] = "healthy" if v.status_code == 200 else "unhealthy"
        except:
            health_status["services"]["verification"] = "unreachable"

    # Overall status
    if all(s == "healthy" for s in health_status["services"].values()):
        health_status["status"] = "healthy"
    else:
        health_status["status"] = "degraded"

    return health_status
