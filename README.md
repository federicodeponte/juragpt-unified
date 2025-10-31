# JuraGPT Unified - Production-Ready Legal Q&A System

**Complete legal question-answering system with built-in hallucination detection**

Combines **juragpt-rag** (325K+ vector retrieval) with **juragpt-auditor** (sentence-level verification) into a unified, production-ready microservices architecture.

## Overview

This system provides end-to-end verified legal answers by:
1. **Retrieving** relevant legal sources from 325,456 vectors (German laws + EUR-Lex)
2. **Generating** answers using an LLM (GPT-4, Claude, etc.)
3. **Verifying** answers against sources with confidence scoring
4. **Returning** verified answers with trust labels

## Architecture

```
juragpt-unified/
├── services/
│   ├── retrieval/          # RAG service (Qdrant + embeddings)
│   ├── verification/       # Hallucination detection
│   ├── embedder/           # Shared E5-large model
│   └── orchestrator/       # API gateway
├── shared/
│   ├── models/             # Pydantic schemas
│   ├── config/             # Unified settings
│   └── utils/              # Common utilities
├── monitoring/
│   ├── prometheus/         # Metrics
│   └── grafana/            # Dashboards
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

### From juragpt-rag (Retrieval Service)
- ✅ 325,456 vectors indexed (274,413 German laws + 51,491 EUR-Lex)
- ✅ GPU-accelerated embedding generation (Modal)
- ✅ Resumable ETL pipelines with checkpointing
- ✅ Incremental daily updates
- ✅ FastAPI retrieval endpoint

### From juragpt-auditor (Verification Service)
- ✅ Sentence-level semantic verification
- ✅ Multi-factor confidence scoring (semantic, retrieval, citations, coverage)
- ✅ SHA-256 source fingerprinting
- ✅ JWT + API key authentication
- ✅ Rate limiting
- ✅ Prometheus metrics
- ✅ 240+ comprehensive tests

### New in Unified System
- ✅ Single API for query → retrieve → verify workflow
- ✅ Shared embedding model (reduce memory footprint)
- ✅ Unified authentication
- ✅ Comprehensive monitoring stack
- ✅ Docker Compose deployment
- ✅ Integration tests

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

See [docs/UPDATE_GUIDE.md](docs/UPDATE_GUIDE.md) for details.

## Project Status

- [x] Phase 1: Repository setup ✅
- [ ] Phase 2: Service migration
- [ ] Phase 3: Shared embedder service
- [ ] Phase 4: Orchestrator API
- [ ] Phase 5: Docker Compose setup
- [ ] Phase 6: Integration tests
- [ ] Phase 7: Documentation
- [ ] Phase 8: Production deployment

**Current Status**: Foundation created, ready for service migration

## Documentation

- [ARCHITECTURE.md](docs/ARCHITECTURE.md) - System design and architecture
- [API.md](docs/API.md) - Complete API reference
- [DEPLOYMENT.md](docs/DEPLOYMENT.md) - Deployment guide
- [UPDATE_GUIDE.md](docs/UPDATE_GUIDE.md) - Corpus update procedures
- [MIGRATION_GUIDE.md](docs/MIGRATION_GUIDE.md) - How we merged the repositories

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md)

## License

MIT License - See [LICENSE](LICENSE)

## Contact

- **Repository**: https://github.com/federicodeponte/juragpt-unified
- **Issues**: https://github.com/federicodeponte/juragpt-unified/issues

## Acknowledgments

This project combines:
- **juragpt-rag**: Legal corpus ingestion and retrieval (https://github.com/federicodeponte/juragpt-rag)
- **juragpt-auditor**: Hallucination detection for legal AI (https://github.com/federicodeponte/juragpt-auditor)

---

**Built with ❤️ for legal professionals who demand accuracy**
