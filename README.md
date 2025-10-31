# JuraGPT Unified - Production-Ready Legal AI System

**ChatGPT for Lawyers: Complete legal AI platform with document processing, knowledge retrieval, and hallucination detection**

Integrates **juragpt-backend** (secure chatbot), **juragpt-rag** (325K+ vector retrieval), and **juragpt-auditor** (sentence-level verification) into a unified, production-ready microservices architecture.

## Overview

JuraGPT is an AI-powered legal assistant system that provides:

1. **Document Processing** - Secure chatbot with file reading, large context windows, and GDPR-compliant PII protection
2. **Knowledge Enrichment** - Semantic retrieval from 325,456 legal document vectors (German Federal Laws + EUR-Lex)
3. **Answer Generation** - LLM-powered responses using Gemini 2.5 Pro with legal context
4. **Hallucination Protection** - Sentence-level verification with multi-factor confidence scoring
5. **Verified Responses** - Trust-labeled answers with source citations and confidence metrics

## Architecture

```
juragpt-unified/
├── services/
│   ├── document/           # Chatbot service (FastAPI, Gemini 2.5 Pro, PII protection)
│   ├── retrieval/          # RAG service (Qdrant + 325K vectors)
│   ├── verification/       # Hallucination detection (sentence-level)
│   ├── embedder/           # Shared multilingual-e5-large model
│   └── orchestrator/       # API gateway (coordinates all services)
├── tests/
│   ├── document/           # Document service tests (21 files)
│   ├── integration/        # Cross-service tests
│   └── e2e/                # End-to-end workflows
├── shared/
│   ├── models/             # Pydantic schemas
│   ├── config/             # Unified settings
│   └── utils/              # Common utilities
├── monitoring/
│   ├── prometheus/         # Metrics collection
│   └── grafana/            # Performance dashboards
└── docker-compose.yml      # Full stack deployment
```

### Technology Stack

- **Python 3.11** - All services
- **FastAPI** - REST APIs with async support
- **Qdrant Cloud** - Vector database (retrieval)
- **PostgreSQL** - Verification history
- **multilingual-e5-large** - Embeddings (768-dim, shared)
- **spaCy** - German NLP (sentence segmentation)
- **Modal** - GPU acceleration for embeddings
- **Docker + Compose** - Deployment
- **Prometheus + Grafana** - Monitoring

## Features

### From juragpt-backend (Document Service)
- ✅ Secure chatbot with large context windows (Gemini 2.5 Pro)
- ✅ GDPR-compliant PII protection (Presidio + German NLP)
- ✅ Multi-format document processing (PDF, DOCX, images)
- ✅ GPU-accelerated OCR pipeline (Modal + docTR + TrOCR)
- ✅ Hierarchical RAG for legal documents (§, Absätze, Ziffern)
- ✅ Multi-tenancy with Row-Level Security (RLS)
- ✅ Private document indexing (Supabase pgvector)
- ✅ JWT authentication + rate limiting + quota tracking
- ✅ Prometheus metrics + Sentry error tracking
- ✅ 21 comprehensive tests (86% pass rate)

### From juragpt-rag (Retrieval Service)
- ✅ 325,456 vectors indexed (274,413 German laws + 51,491 EUR-Lex)
- ✅ GPU-accelerated embedding generation (Modal)
- ✅ Resumable ETL pipelines with checkpointing
- ✅ Incremental daily updates
- ✅ FastAPI retrieval endpoint
- ✅ Hierarchical parent-child chunk relationships

### From juragpt-auditor (Verification Service)
- ✅ Sentence-level semantic verification
- ✅ Multi-factor confidence scoring (semantic, retrieval, citations, coverage)
- ✅ SHA-256 source fingerprinting
- ✅ JWT + API key authentication
- ✅ Rate limiting
- ✅ Prometheus metrics
- ✅ 240+ comprehensive tests

### New in Unified System
- ✅ Complete legal AI pipeline: upload → process → enrich → generate → verify
- ✅ Shared embedding model (reduce memory footprint)
- ✅ Unified authentication across all services
- ✅ Comprehensive monitoring stack (Prometheus + Grafana + Sentry)
- ✅ Docker Compose deployment
- ✅ Integration tests across services

## Quick Start

### Prerequisites

- Python 3.11+
- Docker + Docker Compose
- Qdrant Cloud account
- PostgreSQL 15+
- Modal account (for GPU embeddings)

### Installation

```bash
# Clone repository
git clone https://github.com/federicodeponte/juragpt-unified.git
cd juragpt-unified

# Run migration script to copy services
./scripts/migrate_services.sh

# Set up environment
cp .env.example .env
# Edit .env with your credentials

# Install dependencies
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Deploy with Docker Compose
docker-compose up -d
```

### Usage

```python
import requests

# Full pipeline: retrieve → generate → verify
response = requests.post(
    "http://localhost:8888/query",
    json={
        "query": "Wann haftet jemand nach §823 BGB?",
        "generate_answer": True,
        "verify_answer": True
    },
    headers={"Authorization": "Bearer YOUR_JWT_TOKEN"}
)

result = response.json()
print(f"Answer: {result['answer']}")
print(f"Confidence: {result['verification']['confidence']}")
print(f"Trust: {result['verification']['trust_label']}")
print(f"Sources: {len(result['sources'])}")
```

## API Endpoints

### Orchestrator (Port 8888)
- `POST /query` - Full pipeline (retrieve + generate + verify)
- `POST /retrieve` - Retrieval only
- `POST /verify` - Verification only
- `GET /health` - System health check

### Retrieval Service (Port 8001)
- `POST /retrieve` - Semantic search over 325K+ vectors
- `GET /stats` - Corpus statistics

### Verification Service (Port 8002)
- `POST /verify` - Sentence-level verification
- `GET /metrics` - Prometheus metrics

### Embedder Service (Port 8003)
- `POST /embed` - Generate embeddings (shared by all services)

## Data Sources

### Current (Active)
- **German Federal Laws**: 274,413 vectors (kmein/gesetze GitHub)
- **EUR-Lex**: 51,491 vectors (57K EU law documents)

### Future (When Available)
- **OpenLegalData API**: 57K laws + 251K court cases (currently down)

## Monitoring

Access Grafana dashboards:
```
http://localhost:3000
```

**Default credentials**: admin/admin

**Dashboards available**:
- System overview (requests, latency, errors)
- Retrieval performance (vector DB hit rate, query latency)
- Verification metrics (confidence distribution, low-confidence alerts)
- Resource usage (CPU, memory, GPU)

## Development

### Running Tests

```bash
# Unit tests
pytest tests/unit/

# Integration tests
pytest tests/integration/

# E2E tests
pytest tests/e2e/

# All tests with coverage
pytest --cov=services --cov-report=html
```

### Code Quality

```bash
# Format code
black services/ shared/

# Lint
ruff check services/ shared/

# Type check
mypy services/ shared/
```

## Configuration

### Environment Variables

```bash
# Qdrant (Vector Database)
QDRANT_URL=https://your-cluster.qdrant.io
QDRANT_API_KEY=your-api-key

# PostgreSQL (Verification History)
DATABASE_URL=postgresql://user:password@localhost:5432/juragpt

# Embeddings
EMBEDDING_MODEL=intfloat/multilingual-e5-large
EMBEDDER_URL=http://embedder:8003

# Authentication
JWT_SECRET_KEY=your-secret-key
ENABLE_AUTH=true

# Monitoring
ENABLE_METRICS=true

# Feature Flags
ENABLE_RETRIEVAL=true
ENABLE_VERIFICATION=true
```

## Deployment

### Docker Compose (Recommended)

```bash
docker-compose up -d
```

### Kubernetes (Production)

```bash
kubectl apply -f k8s/
```

### Manual Service Deployment

```bash
# Retrieval service
cd services/retrieval
uvicorn main:app --host 0.0.0.0 --port 8001

# Verification service
cd services/verification
uvicorn main:app --host 0.0.0.0 --port 8002

# Embedder service
cd services/embedder
uvicorn main:app --host 0.0.0.0 --port 8003

# Orchestrator
cd services/orchestrator
uvicorn main:app --host 0.0.0.0 --port 8888
```

## Update Strategy

**Recommended**: Monthly manual updates

```bash
./scripts/update_corpus.sh
```

**Cost**: $2-10 per update (Modal GPU usage)

Detailed update procedures will be documented in Phase 9.

## Project Status

- [x] Phase 1: Repository setup ✅
- [x] Phase 2: Service migration ✅
- [x] Phase 3: Shared embedder service ✅
- [x] Phase 4: Orchestrator API ✅
- [x] Phase 5: Docker Compose setup ✅
- [x] Phase 6: Smoke tests ✅
- [ ] Phase 7: Integration tests (E2E)
- [ ] Phase 8: Production deployment testing
- [ ] Phase 9: Documentation (ARCHITECTURE.md, API.md, etc.)

**Current Status**: Core services merged and tested (smoke tests passing). Ready for integration testing and deployment verification.

## Documentation

Full documentation (ARCHITECTURE.md, API.md, DEPLOYMENT.md, UPDATE_GUIDE.md) will be added in Phase 9.

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md)

## License

MIT License - See [LICENSE](LICENSE)

## Contact

- **Repository**: https://github.com/federicodeponte/juragpt-unified
- **Issues**: https://github.com/federicodeponte/juragpt-unified/issues

## Acknowledgments

This project combines three foundational systems:
- **juragpt-backend**: Secure chatbot with PII protection and OCR (integrated as Document Service)
- **juragpt-rag**: Legal corpus ingestion and retrieval (https://github.com/federicodeponte/juragpt-rag)
- **juragpt-auditor**: Hallucination detection for legal AI (https://github.com/federicodeponte/juragpt-auditor)

---

**Built with ❤️ for legal professionals who demand accuracy**
