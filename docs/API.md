# JuraGPT Unified - API Reference

Complete REST API documentation for all microservices.

## Base URLs

- **Orchestrator**: `http://localhost:8888` (production entry point)
- **Retrieval**: `http://localhost:8001` (direct access)
- **Verification**: `http://localhost:8002` (direct access)
- **Embedder**: `http://localhost:8003` (internal only)

## Authentication

Currently: None (development mode)
Production: JWT Bearer tokens via Authorization header

```bash
curl -H "Authorization: Bearer YOUR_JWT_TOKEN" ...
```

## Orchestrator API

### POST /query - Unified Query

Complete workflow: retrieve sources → generate answer → verify answer

**Request**:
```json
{
  "query": "Wann haftet jemand nach §823 BGB?",
  "top_k": 5,
  "answer": "Optional pre-generated answer",
  "generate_answer": false,
  "verify_answer": true
}
```

**Response**:
```json
{
  "query": "Wann haftet jemand nach §823 BGB?",
  "sources": [
    {
      "doc_id": "bgb_823",
      "title": "§823 BGB - Schadensersatzpflicht",
      "text": "Wer vorsätzlich oder fahrlässig...",
      "score": 0.95
    }
  ],
  "answer": "Eine Person haftet nach §823 BGB...",
  "verification": {
    "confidence": 0.92,
    "trust_label": "HIGH",
    "verified_claims": 3,
    "unsupported_claims": 0
  }
}
```

### POST /retrieve - Retrieval Only

Pass-through to retrieval service.

### POST /verify - Verification Only

Pass-through to verification service.

### GET /health - System Health

**Response**:
```json
{
  "status": "healthy",
  "services": {
    "retrieval": "healthy",
    "verification": "healthy"
  }
}
```

## Retrieval Service API

### POST /retrieve

Semantic search over 325K+ legal documents.

**Request**:
```json
{
  "query": "Schadensersatz bei Fahrlässigkeit",
  "top_k": 10
}
```

**Response**:
```json
{
  "sources": [
    {
      "doc_id": "bgb_823",
      "title": "§823 BGB",
      "text": "...",
      "score": 0.95,
      "metadata": {
        "source": "german_laws",
        "category": "civil_law"
      }
    }
  ],
  "query_embedding_dim": 1024
}
```

### GET /stats

Corpus statistics.

**Response**:
```json
{
  "total_vectors": 325904,
  "german_laws": 274413,
  "eurlex": 51491,
  "model": "multilingual-e5-large"
}
```

## Verification Service API

### POST /verify

Sentence-level hallucination detection.

**Request**:
```json
{
  "answer": "Nach §823 BGB haftet, wer vorsätzlich handelt.",
  "sources": [
    "§823 BGB: Wer vorsätzlich oder fahrlässig...",
    "§826 BGB: Wer in einer gegen die guten Sitten..."
  ]
}
```

**Response**:
```json
{
  "confidence": 0.87,
  "trust_label": "HIGH",
  "verified_claims": 1,
  "unsupported_claims": 0,
  "sentence_scores": [
    {
      "sentence": "Nach §823 BGB haftet, wer vorsätzlich handelt.",
      "confidence": 0.87,
      "best_match_source": "§823 BGB: Wer vorsätzlich...",
      "semantic_similarity": 0.91
    }
  ]
}
```

### GET /metrics

Prometheus metrics endpoint.

## Embedder Service API

### POST /embed

Generate multilingual-e5-large embeddings.

**Request**:
```json
{
  "texts": ["Legal question here", "Another text"],
  "normalize": true
}
```

**Response**:
```json
{
  "embeddings": [[0.123, -0.456, ...], [0.789, ...]],
  "model": "intfloat/multilingual-e5-large",
  "dimension": 1024
}
```

### GET /health

Service health check.

## Error Responses

All services return consistent error format:

```json
{
  "detail": "Descriptive error message",
  "error_code": "RETRIEVAL_FAILED",
  "timestamp": "2025-10-31T12:00:00Z"
}
```

**Status Codes**:
- 200: Success
- 400: Bad request (invalid input)
- 500: Internal server error
- 503: Service unavailable

## Examples

### Complete Workflow

```bash
curl -X POST http://localhost:8888/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Was ist ein Kaufvertrag?",
    "top_k": 3,
    "verify_answer": true
  }'
```

### Retrieval Only

```bash
curl -X POST http://localhost:8001/retrieve \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Mietrecht",
    "top_k": 5
  }'
```

### Verification Only

```bash
curl -X POST http://localhost:8002/verify \
  -H "Content-Type: application/json" \
  -d '{
    "answer": "Ein Kaufvertrag ist...",
    "sources": ["BGB §433: Der Kaufvertrag..."]
  }'
```

## Rate Limiting

Currently: None
Production: 100 requests/minute per IP

## SDK / Client Libraries

Use any HTTP client:

**Python**:
```python
import requests

response = requests.post(
    "http://localhost:8888/query",
    json={"query": "Legal question", "top_k": 5}
)
result = response.json()
```

**JavaScript**:
```javascript
fetch('http://localhost:8888/query', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({query: "Legal question", top_k: 5})
})
.then(res => res.json())
.then(data => console.log(data))
```

## API Versioning

Current: v1 (implicit, no version in URL)
Future: `/api/v2/query`
