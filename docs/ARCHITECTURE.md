# JuraGPT Unified - Architecture

## System Overview

JuraGPT Unified is a production-ready microservices system that combines **retrieval-augmented generation (RAG)** with **sentence-level hallucination detection** for legal Q&A.

**Core Capability**: Answer legal questions with verified confidence scores by retrieving relevant legal sources and validating LLM-generated answers against those sources.

## Architecture Principles

1. **Microservices**: Each service has a single responsibility and can scale independently
2. **Shared Resources**: Common embedder service eliminates duplication (DRY)
3. **API Gateway Pattern**: Orchestrator coordinates all services
4. **Separation of Concerns**: Retrieval, verification, embeddings, and orchestration are isolated
5. **Production-Ready**: Authentication, monitoring, error handling, health checks

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Client Application                        │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                    ┌───────────▼───────────┐
                    │   Orchestrator API    │ Port 8888
                    │  (API Gateway)        │
                    └─────────┬─────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          │                   │                   │
    ┌─────▼──────┐    ┌──────▼───────┐   ┌─────▼──────┐
    │ Retrieval  │    │Verification  │   │  Embedder  │
    │  Service   │    │   Service    │   │  Service   │
    │ (Port 8001)│    │ (Port 8002)  │   │(Port 8003) │
    └─────┬──────┘    └──────┬───────┘   └─────┬──────┘
          │                  │                  │
    ┌─────▼──────┐    ┌──────▼───────┐   ┌─────▼──────┐
    │   Qdrant   │    │ PostgreSQL   │   │ E5-Large   │
    │  (Vector   │    │(Verification │   │  Model     │
    │  Database) │    │   History)   │   │ (Shared)   │
    └────────────┘    └──────────────┘   └────────────┘
```

## Components

### 1. Orchestrator Service (Port 8888)

**Purpose**: API gateway coordinating all microservices

**Responsibilities**:
- Accept client queries
- Route requests to appropriate services
- Coordinate multi-service workflows
- Return unified responses
- Aggregate health status

**Endpoints**:
- `POST /query` - Full pipeline (retrieve → generate → verify)
- `POST /retrieve` - Retrieval only (pass-through)
- `POST /verify` - Verification only (pass-through)
- `GET /health` - System health check

**Technology**: FastAPI (Python 3.11), async/await, httpx for service communication

**Code**: `services/orchestrator/main.py` (163 lines)

### 2. Retrieval Service (Port 8001)

**Purpose**: Semantic search over 325K+ legal document vectors

**Responsibilities**:
- Convert queries to embeddings (via Embedder service)
- Search Qdrant vector database
- Return top-K relevant sources with scores
- Provide corpus statistics

**Data**:
- 274,413 German federal laws (kmein/gesetze)
- 51,491 EUR-Lex EU law documents
- Total: 325,904 vectors

**Technology**: FastAPI, Qdrant Cloud (gRPC), multilingual-e5-large embeddings (1024-dim)

**Code**: `services/retrieval/src/` (migrated from juragpt-rag)

### 3. Verification Service (Port 8002)

**Purpose**: Hallucination detection via sentence-level semantic verification

**Responsibilities**:
- Segment answers into sentences (spaCy)
- Compare each sentence against source documents
- Calculate multi-factor confidence scores
- Track verification history (PostgreSQL)
- Expose Prometheus metrics

**Confidence Factors**:
- Semantic similarity (cosine distance)
- Retrieval scores (source quality)
- Citation presence
- Coverage ratio (answer/source alignment)

**Technology**: FastAPI, spaCy (German NLP), sentence-transformers, PostgreSQL, Prometheus

**Code**: `services/verification/auditor/` (migrated from juragpt-auditor)

### 4. Embedder Service (Port 8003)

**Purpose**: Shared embedding generation for both retrieval and verification

**Responsibilities**:
- Load multilingual-e5-large model once
- Generate 1024-dim embeddings
- Serve both retrieval and verification services
- Reduce memory footprint by sharing model

**Why Shared**: Previously, both services loaded the same model independently (2x memory). Now one instance serves both.

**Technology**: FastAPI, sentence-transformers, multilingual-e5-large (1.1GB model)

**Code**: `services/embedder/main.py` (72 lines)

### 5. Supporting Infrastructure

**Qdrant Cloud** (External):
- Vector database with gRPC protocol
- 325K+ indexed vectors
- Configured via QDRANT_URL and QDRANT_API_KEY

**PostgreSQL** (Docker):
- Verification history
- User authentication (future)
- Audit logs

**Prometheus + Grafana** (Docker):
- Metrics collection
- Performance dashboards
- Alert management

## Data Flow

### Complete Query Flow

```
1. Client → Orchestrator
   POST /query {"query": "Legal question", "verify_answer": true}

2. Orchestrator → Retrieval Service
   POST /retrieve {"query": "Legal question", "top_k": 5}

3. Retrieval → Embedder Service
   POST /embed {"texts": ["Legal question"]}

4. Embedder → Retrieval
   {"embeddings": [[0.123, ...]], "dimension": 1024}

5. Retrieval → Qdrant
   search(vector, limit=5)

6. Qdrant → Retrieval
   [{"id": "doc_1", "score": 0.95, "payload": {...}}, ...]

7. Retrieval → Orchestrator
   {"sources": [{"doc_id": "bgb_823", "text": "...", "score": 0.95}]}

8. Orchestrator → (External LLM - optional)
   Generate answer based on sources

9. Orchestrator → Verification Service
   POST /verify {"answer": "...", "sources": ["source1", "source2"]}

10. Verification → Embedder Service
    POST /embed {"texts": ["sentence1", "sentence2", ...]}

11. Verification calculates confidence → Orchestrator
    {"confidence": 0.92, "trust_label": "HIGH"}

12. Orchestrator → Client
    {
      "query": "...",
      "sources": [...],
      "answer": "...",
      "verification": {"confidence": 0.92, "trust_label": "HIGH"}
    }
```

## Deployment Architecture

### Development

```bash
# Local services without Docker
python services/embedder/main.py &  # Port 8003
python services/retrieval/main.py &  # Port 8001
python services/verification/main.py &  # Port 8002
python services/orchestrator/main.py &  # Port 8888
```

### Production (Docker Compose)

```yaml
services:
  embedder:       # Shared model (8GB RAM limit)
  retrieval:      # Depends on embedder + qdrant
  verification:   # Depends on embedder + postgres
  orchestrator:   # Depends on retrieval + verification
  postgres:       # Persistent storage
  qdrant:         # Optional (or use Qdrant Cloud)
  prometheus:     # Metrics collection
  grafana:        # Dashboards
```

**Resource Requirements** (Production):
- Embedder: 8GB RAM (model + overhead)
- Retrieval: 2GB RAM
- Verification: 2GB RAM
- Orchestrator: 1GB RAM
- PostgreSQL: 2GB RAM
- Total: ~15GB RAM minimum

## Scaling Strategy

### Horizontal Scaling

**Embedder**: Stateless - can run multiple instances behind load balancer
**Retrieval**: Stateless - multiple instances possible (Qdrant Cloud handles scaling)
**Verification**: Mostly stateless - database writes can be queued
**Orchestrator**: Fully stateless - unlimited scaling possible

### Vertical Scaling

**Embedder**: More RAM = larger batches, faster processing
**Qdrant**: More memory/CPU = faster vector search
**PostgreSQL**: More storage for verification history

### Bottlenecks

1. **Embedder Service**: Model inference is CPU/GPU bound - consider GPU acceleration
2. **Qdrant Search**: Vector search scales with index size - monitor query latency
3. **Database Writes**: Verification history writes - consider async queue

## Security

### Current Implementation

- Environment-based configuration (secrets in .env)
- CORS headers on all services
- Input validation via Pydantic models
- Error handling with proper HTTP status codes

### Production Requirements

- [ ] JWT authentication on all endpoints
- [ ] Rate limiting (per-user/IP)
- [ ] Row-level security in PostgreSQL
- [ ] API key rotation
- [ ] TLS/HTTPS enforcement
- [ ] Network isolation (Docker networks)
- [ ] Secrets management (HashiCorp Vault, AWS Secrets Manager)

## Monitoring

### Metrics Collected

**Service-Level** (All services):
- Request count
- Response time (p50, p95, p99)
- Error rate
- Active connections

**Domain-Specific**:
- Verification confidence distribution
- Low-confidence alert frequency
- Retrieval hit rate
- Embedding batch size/throughput

### Health Checks

Each service exposes `GET /health`:
```json
{
  "status": "healthy|degraded|unhealthy",
  "service": "embedder|retrieval|verification|orchestrator",
  "dependencies": {
    "database": "connected|disconnected",
    "qdrant": "reachable|unreachable"
  }
}
```

## Error Handling

### Retry Strategy

- **Retrieval Service Down**: Return cached results (if available) or fail gracefully
- **Verification Service Down**: Return unverified answer with warning
- **Embedder Service Down**: All dependent services fail (critical dependency)

### Graceful Degradation

- If verification fails → return answer without confidence score
- If retrieval finds 0 results → return "no relevant sources" message
- If embedder is slow → timeout after 30s and retry

## Testing Strategy

### Unit Tests

- `tests/test_smoke.py` - Service structure and imports (5 tests)

### Integration Tests

- `tests/test_integration_orchestrator.py` - Full workflow testing (5 tests)
  - Unified query workflow
  - Retrieval-only mode
  - Error handling
  - Health endpoint (healthy state)
  - Health endpoint (degraded state)

### E2E Tests (Future)

- [ ] Real Qdrant queries
- [ ] Real PostgreSQL writes
- [ ] End-to-end with actual LLM
- [ ] Load testing (Locust)

## Migration from Source Projects

### From juragpt-rag

**Copied**:
- `services/retrieval/src/` - All RAG code
- `services/retrieval/scripts/` - Data ingestion scripts
- Data ingestion pipelines (German laws + EUR-Lex)

**Modified**:
- Removed local embedding generation (now uses Embedder service)
- Configured to use shared embedder at `http://embedder:8003`

### From juragpt-auditor

**Copied**:
- `services/verification/auditor/` - All verification code
- `services/verification/tests/` - 240+ tests
- PostgreSQL schema and migrations

**Modified**:
- Removed local embedding generation (now uses Embedder service)
- Configured to use shared embedder at `http://embedder:8003`

### New Code Written

- `services/embedder/main.py` (72 lines) - Shared embedding service
- `services/orchestrator/main.py` (163 lines) - API gateway
- `tests/test_smoke.py` (150 lines) - Smoke tests
- `tests/test_integration_orchestrator.py` (261 lines) - Integration tests
- `scripts/migrate_services.sh` (400+ lines) - Automated migration

**Total New Code**: ~1,046 lines (minimal, focused on integration)

## Design Decisions

### Why Microservices?

**Pros**:
- Independent scaling (embedder needs more RAM)
- Clear separation of concerns
- Easier testing (mock service boundaries)
- Team can work on services independently

**Cons**:
- Network overhead between services
- More complex deployment
- Service discovery required

**Decision**: Benefits outweigh costs for production use

### Why Shared Embedder?

**Alternative**: Each service loads model independently

**Problem**: 2x memory usage (2.2GB total vs 1.1GB shared)

**Solution**: Single embedder service serves both retrieval and verification

**Trade-off**: Introduces single point of failure, but acceptable with proper monitoring

### Why FastAPI?

- Async/await for concurrent requests
- Automatic OpenAPI documentation
- Pydantic for type safety
- Wide Python ecosystem support
- Production-proven

## Future Enhancements

### Phase 1 (Short-term)

- [ ] Add JWT authentication
- [ ] Implement rate limiting
- [ ] Add Redis caching layer
- [ ] GPU acceleration for embeddings (Modal)

### Phase 2 (Medium-term)

- [ ] Multi-tenancy support
- [ ] Custom fine-tuned models
- [ ] Advanced monitoring (distributed tracing)
- [ ] Automated scaling (Kubernetes HPA)

### Phase 3 (Long-term)

- [ ] Multi-language support (beyond German)
- [ ] Real-time updates (websockets)
- [ ] Federated search across multiple legal systems
- [ ] AI-powered answer generation (integrated LLM)

## References

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Qdrant Documentation](https://qdrant.tech/documentation/)
- [multilingual-e5-large Model](https://huggingface.co/intfloat/multilingual-e5-large)
- [Source: juragpt-rag](https://github.com/federicodeponte/juragpt-rag)
- [Source: juragpt-auditor](https://github.com/federicodeponte/juragpt-auditor)
