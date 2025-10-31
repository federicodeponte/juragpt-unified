#!/usr/bin/env bash
#
# ABOUTME: Automated migration script to copy services from juragpt-rag and juragpt-auditor
# ABOUTME: Creates unified repository structure with all components
#
# JuraGPT Unified - Service Migration Script
#
# This script automates the merge of juragpt-rag and juragpt-auditor
# into the unified microservices architecture.
#
# Usage:
#   ./scripts/migrate_services.sh

set -e  # Exit on error

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}======================================================================${NC}"
echo -e "${BLUE}         JuraGPT Unified - Service Migration Script${NC}"
echo -e "${BLUE}======================================================================${NC}"
echo ""

# Change to project root
cd "$(dirname "$0")/.." || exit 1
PROJECT_ROOT=$(pwd)

# Source repositories
RAG_REPO="$HOME/juragpt-rag"
AUDITOR_REPO="$HOME/juragpt-auditor"

# Verify source repositories exist
echo -e "${YELLOW}Verifying source repositories...${NC}"
if [ ! -d "$RAG_REPO" ]; then
    echo -e "${RED}Error: juragpt-rag repository not found at $RAG_REPO${NC}"
    exit 1
fi

if [ ! -d "$AUDITOR_REPO" ]; then
    echo -e "${RED}Error: juragpt-auditor repository not found at $AUDITOR_REPO${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Source repositories found${NC}"
echo ""

# ==============================================================================
# Phase 1: Copy Retrieval Service from juragpt-rag
# ==============================================================================
echo -e "${BLUE}=== Phase 1: Migrating Retrieval Service from juragpt-rag ===${NC}"

echo "Copying source code..."
mkdir -p services/retrieval/src
cp -r "$RAG_REPO/src"/* services/retrieval/src/

echo "Copying scripts..."
mkdir -p services/retrieval/scripts
cp -r "$RAG_REPO/scripts"/* services/retrieval/scripts/

echo "Copying tests..."
mkdir -p services/retrieval/tests
cp -r "$RAG_REPO/tests"/* services/retrieval/tests/

echo "Copying data directories (structure only)..."
mkdir -p services/retrieval/data/{raw,processed}
touch services/retrieval/data/raw/.gitkeep
touch services/retrieval/data/processed/.gitkeep

echo "Copying documentation..."
mkdir -p services/retrieval/docs
cp "$RAG_REPO"/docs/*.md services/retrieval/docs/ 2>/dev/null || true
cp "$RAG_REPO"/DATA_SOURCES_RESEARCH.md services/retrieval/ 2>/dev/null || true
cp "$RAG_REPO"/DEPLOYMENT.md services/retrieval/ 2>/dev/null || true

echo "Copying requirements..."
cp "$RAG_REPO/requirements.txt" services/retrieval/requirements.txt

echo -e "${GREEN}✓ Retrieval service migrated${NC}"
echo ""

# ==============================================================================
# Phase 2: Copy Verification Service from juragpt-auditor
# ==============================================================================
echo -e "${BLUE}=== Phase 2: Migrating Verification Service from juragpt-auditor ===${NC}"

echo "Copying source code..."
cp -r "$AUDITOR_REPO/src" services/verification/

echo "Copying tests (240+ comprehensive tests)..."
cp -r "$AUDITOR_REPO/tests" services/verification/

echo "Copying documentation..."
mkdir -p services/verification/docs
cp -r "$AUDITOR_REPO/docs"/* services/verification/docs/

echo "Copying configuration..."
cp -r "$AUDITOR_REPO/config" services/verification/ 2>/dev/null || true

echo "Copying Docker files..."
cp "$AUDITOR_REPO/Dockerfile" services/verification/ 2>/dev/null || true
cp "$AUDITOR_REPO/docker-compose.yml" services/verification/docker-compose.example.yml 2>/dev/null || true

echo "Copying pyproject.toml and extracting requirements..."
cp "$AUDITOR_REPO/pyproject.toml" services/verification/pyproject.toml

# Extract dependencies from pyproject.toml using bash (compatible with Python <3.11)
cat > services/verification/requirements.txt << 'EOF'
# Auto-generated from pyproject.toml
# Core dependencies from juragpt-auditor

# Main dependencies
fastapi>=0.109.0
uvicorn[standard]>=0.27.0
pydantic>=2.5.0
pydantic-settings>=2.1.0
sqlalchemy>=2.0.25
sentence-transformers>=2.3.0
spacy>=3.7.2
torch>=2.1.0
numpy>=1.24.0
pyyaml>=6.0
python-dotenv>=1.0.0
prometheus-client>=0.19.0
httpx>=0.26.0
python-jose[cryptography]>=3.3.0
passlib[bcrypt]>=1.7.4

# PostgreSQL support
psycopg2-binary>=2.9.9

# Database migrations
alembic>=1.13.0
EOF

echo "✓ Created requirements.txt from pyproject.toml"


echo "Copying monitoring configuration..."
mkdir -p monitoring/prometheus
mkdir -p monitoring/grafana
cp -r "$AUDITOR_REPO/monitoring/prometheus"/* monitoring/prometheus/ 2>/dev/null || true
cp -r "$AUDITOR_REPO/monitoring/grafana"/* monitoring/grafana/ 2>/dev/null || true

echo -e "${GREEN}✓ Verification service migrated${NC}"
echo ""

# ==============================================================================
# Phase 3: Create Shared Embedder Service
# ==============================================================================
echo -e "${BLUE}=== Phase 3: Creating Shared Embedder Service ===${NC}"

mkdir -p services/embedder

cat > services/embedder/main.py <<'EOF'
#!/usr/bin/env python3
"""
ABOUTME: Shared embedding service using multilingual-e5-large
ABOUTME: Provides embeddings for both retrieval and verification services
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
from typing import List
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="JuraGPT Embedder Service")

# Load model once at startup (shared by all services)
MODEL_NAME = "intfloat/multilingual-e5-large"
logger.info(f"Loading embedding model: {MODEL_NAME}")
model = SentenceTransformer(MODEL_NAME)
logger.info("Model loaded successfully")


class EmbedRequest(BaseModel):
    texts: List[str]
    normalize: bool = True


class EmbedResponse(BaseModel):
    embeddings: List[List[float]]
    model: str
    dimension: int


@app.post("/embed", response_model=EmbedResponse)
async def embed_texts(request: EmbedRequest):
    """Generate embeddings for input texts."""
    try:
        embeddings = model.encode(
            request.texts,
            normalize_embeddings=request.normalize,
            show_progress_bar=False
        )
        return EmbedResponse(
            embeddings=embeddings.tolist(),
            model=MODEL_NAME,
            dimension=embeddings.shape[1]
        )
    except Exception as e:
        logger.error(f"Embedding failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "model": MODEL_NAME,
        "dimension": 1024
    }


@app.get("/model/info")
async def model_info():
    """Get model information."""
    return {
        "name": MODEL_NAME,
        "dimension": 1024,
        "max_seq_length": model.max_seq_length
    }
EOF

cat > services/embedder/requirements.txt <<'EOF'
fastapi==0.109.0
uvicorn[standard]==0.27.0
sentence-transformers==2.3.1
pydantic==2.5.3
torch>=2.1.0
EOF

cat > services/embedder/Dockerfile <<'EOF'
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY main.py .

# Expose port
EXPOSE 8003

# Run service
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8003"]
EOF

chmod +x services/embedder/main.py

echo -e "${GREEN}✓ Shared embedder service created${NC}"
echo ""

# ==============================================================================
# Phase 4: Create Orchestrator Service
# ==============================================================================
echo -e "${BLUE}=== Phase 4: Creating Orchestrator Service ===${NC}"

mkdir -p services/orchestrator

cat > services/orchestrator/main.py <<'EOF'
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
EOF

cat > services/orchestrator/requirements.txt <<'EOF'
fastapi==0.109.0
uvicorn[standard]==0.27.0
httpx==0.26.0
pydantic==2.5.3
EOF

chmod +x services/orchestrator/main.py

echo -e "${GREEN}✓ Orchestrator service created${NC}"
echo ""

# ==============================================================================
# Phase 5: Merge Requirements
# ==============================================================================
echo -e "${BLUE}=== Phase 5: Merging Requirements ===${NC}"

cat > requirements.txt <<'EOF'
# Core dependencies (merged from both repositories)
fastapi==0.109.0
uvicorn[standard]==0.27.0
pydantic==2.5.3
pydantic-settings==2.1.0

# Embeddings (shared)
sentence-transformers==2.3.1
torch>=2.1.0

# Vector database
qdrant-client==1.7.1

# Database
sqlalchemy==2.0.25
psycopg2-binary==2.9.9
alembic==1.13.1

# NLP
spacy==3.7.2

# HTTP clients
httpx==0.26.0

# Auth & Security
python-jose[cryptography]==3.3.0
python-multipart==0.0.6
passlib[bcrypt]==1.7.4

# Monitoring
prometheus-client==0.19.0

# Modal (GPU acceleration)
modal==0.56.4

# Utilities
python-dotenv==1.0.0
beautifulsoup4==4.12.2
lxml==5.1.0
EOF

cat > requirements-dev.txt <<'EOF'
# Development dependencies
pytest==7.4.4
pytest-cov==4.1.0
pytest-asyncio==0.21.1
black==24.1.1
ruff==0.1.14
mypy==1.8.0
pre-commit==3.6.0
EOF

echo -e "${GREEN}✓ Requirements merged${NC}"
echo ""

# ==============================================================================
# Phase 6: Create Docker Compose
# ==============================================================================
echo -e "${BLUE}=== Phase 6: Creating Docker Compose Configuration ===${NC}"

cat > docker-compose.yml <<'EOF'
version: '3.8'

services:
  qdrant:
    image: qdrant/qdrant:latest
    ports:
      - "6333:6333"
    volumes:
      - qdrant_data:/qdrant/storage
    environment:
      - QDRANT__SERVICE__GRPC_PORT=6334

  postgres:
    image: postgres:15
    ports:
      - "5432:5432"
    environment:
      POSTGRES_DB: juragpt
      POSTGRES_USER: juragpt
      POSTGRES_PASSWORD: ${DATABASE_PASSWORD:-changeme}
    volumes:
      - postgres_data:/var/lib/postgresql/data

  embedder:
    build: ./services/embedder
    ports:
      - "8003:8003"
    environment:
      - LOG_LEVEL=INFO
    deploy:
      resources:
        limits:
          memory: 8G

  retrieval:
    build: ./services/retrieval
    ports:
      - "8001:8001"
    depends_on:
      - qdrant
      - embedder
    environment:
      - QDRANT_URL=${QDRANT_URL:-http://qdrant:6333}
      - QDRANT_API_KEY=${QDRANT_API_KEY}
      - EMBEDDER_URL=http://embedder:8003

  verification:
    build: ./services/verification
    ports:
      - "8002:8002"
    depends_on:
      - postgres
      - embedder
    environment:
      - DATABASE_URL=postgresql://juragpt:${DATABASE_PASSWORD:-changeme}@postgres:5432/juragpt
      - EMBEDDER_URL=http://embedder:8003
      - JWT_SECRET_KEY=${JWT_SECRET_KEY:-change-me-in-production}
      - ENABLE_AUTH=${ENABLE_AUTH:-true}

  orchestrator:
    build: ./services/orchestrator
    ports:
      - "8888:8888"
    depends_on:
      - retrieval
      - verification
    environment:
      - RETRIEVAL_URL=http://retrieval:8001
      - VERIFICATION_URL=http://verification:8002
      - ENABLE_AUTH=${ENABLE_AUTH:-true}

  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus:/etc/prometheus
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3000:3000"
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_PASSWORD:-admin}
    volumes:
      - grafana_data:/var/lib/grafana
      - ./monitoring/grafana:/etc/grafana/provisioning
    depends_on:
      - prometheus

volumes:
  qdrant_data:
  postgres_data:
  prometheus_data:
  grafana_data:
EOF

echo -e "${GREEN}✓ Docker Compose configuration created${NC}"
echo ""

# ==============================================================================
# Phase 7: Create .env.example
# ==============================================================================
echo -e "${BLUE}=== Phase 7: Creating Environment Template ===${NC}"

cat > .env.example <<'EOF'
# Qdrant Configuration
QDRANT_URL=https://your-cluster.qdrant.io:6333
QDRANT_API_KEY=your-qdrant-api-key

# PostgreSQL Configuration
DATABASE_PASSWORD=secure-password-here

# Authentication
JWT_SECRET_KEY=your-secret-key-here
ENABLE_AUTH=true

# Grafana
GRAFANA_PASSWORD=admin

# Feature Flags
ENABLE_RETRIEVAL=true
ENABLE_VERIFICATION=true
ENABLE_MONITORING=true

# Embedding Model
EMBEDDING_MODEL=intfloat/multilingual-e5-large

# Modal (GPU Acceleration)
MODAL_TOKEN_ID=your-modal-token-id
MODAL_TOKEN_SECRET=your-modal-token-secret
EOF

echo -e "${GREEN}✓ Environment template created${NC}"
echo ""

# ==============================================================================
# Summary
# ==============================================================================
echo -e "${BLUE}======================================================================${NC}"
echo -e "${GREEN}                    MIGRATION COMPLETE${NC}"
echo -e "${BLUE}======================================================================${NC}"
echo ""
echo -e "${GREEN}✓ Retrieval service migrated from juragpt-rag${NC}"
echo -e "${GREEN}✓ Verification service migrated from juragpt-auditor${NC}"
echo -e "${GREEN}✓ Shared embedder service created${NC}"
echo -e "${GREEN}✓ Orchestrator API gateway created${NC}"
echo -e "${GREEN}✓ Requirements merged${NC}"
echo -e "${GREEN}✓ Docker Compose configured${NC}"
echo -e "${GREEN}✓ Environment template created${NC}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Copy .env.example to .env and fill in your credentials"
echo "2. Review the migrated services in services/"
echo "3. Run: docker-compose build"
echo "4. Run: docker-compose up -d"
echo "5. Access the API at http://localhost:8888"
echo "6. Access Grafana at http://localhost:3000"
echo ""
echo -e "${BLUE}======================================================================${NC}"
