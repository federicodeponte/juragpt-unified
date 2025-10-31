# API Reference

Complete API reference for the JuraGPT Auditor verification service.

## Table of Contents

- [Overview](#overview)
- [Base URL](#base-url)
- [Authentication](#authentication)
  - [Method 1: JWT Bearer Token](#method-1-jwt-bearer-token)
  - [Method 2: API Key](#method-2-api-key)
  - [Demo Users](#demo-users)
  - [Scopes](#scopes)
- [Endpoints](#endpoints)
  - [POST /verify](#post-verify)
  - [GET /health](#get-health)
  - [GET /metrics](#get-metrics)
  - [GET /docs](#get-docs)
  - [POST /auth/login](#post-authlogin)
  - [POST /auth/refresh](#post-authrefresh)
  - [POST /auth/api-keys](#post-authapi-keys)
  - [GET /auth/api-keys](#get-authapi-keys)
  - [DELETE /auth/api-keys/{key_id}](#delete-authapi-keyskey_id)
  - [GET /auth/me](#get-authme)
- [Request Models](#request-models)
- [Response Models](#response-models)
- [Error Handling](#error-handling)
- [Rate Limiting](#rate-limiting)
  - [Configuration](#configuration)
  - [Default Limits](#default-limits)
  - [Custom Limits](#custom-limits)
  - [Rate Limit Headers](#rate-limit-headers)
  - [Burst Protection](#burst-protection)
- [Security Headers](#security-headers)
  - [Applied Headers](#applied-headers)
  - [Content Security Policy](#content-security-policy-csp)
  - [CORS](#cors-cross-origin-resource-sharing)
  - [OWASP Top 10 Compliance](#owasp-top-10-compliance)
- [Examples](#examples)
- [Client Libraries](#client-libraries)

---

## Overview

The JuraGPT Auditor API is a REST API built with FastAPI that provides sentence-level semantic verification of LLM-generated answers against trusted source documents.

**Key Features:**

- RESTful JSON API
- Automatic OpenAPI documentation
- Type-safe request/response models (Pydantic)
- Comprehensive error handling
- Prometheus metrics integration

**API Version**: v0.1.0

---

## Base URL

### Production

```
https://api.juragpt.example.com
```

### Docker Compose (Local)

```
http://localhost:8888
```

### Development

```
http://localhost:8000
```

---

## Authentication

### Overview

Authentication is **optional** and **disabled by default**. Enable it in production via environment variables.

The API supports two authentication methods that can be used interchangeably:

1. **JWT Bearer Tokens** - Short-lived tokens for user sessions
2. **API Keys** - Long-lived keys for programmatic access

Both methods use the same endpoints and provide the same access levels based on user scopes.

### Configuration

**Enable Authentication** (`.env`):

```bash
ENABLE_AUTH=true
JWT_SECRET_KEY=your-secret-key-min-32-chars-change-in-production
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
```

**Default**: Authentication is disabled for backward compatibility and local development.

### Method 1: JWT Bearer Token

Use JWT tokens for user sessions with automatic expiration.

**Obtain Token**:

```bash
curl -X POST http://localhost:8888/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'
```

**Response**:

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

**Use Token**:

```bash
curl -X POST http://localhost:8888/verify \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..." \
  -H "Content-Type: application/json" \
  -d @request.json
```

### Method 2: API Key

Use API keys for programmatic access with custom rate limits and expiration.

**Create API Key** (requires admin JWT token):

```bash
curl -X POST http://localhost:8888/auth/api-keys \
  -H "Authorization: Bearer <admin-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-app",
    "scopes": ["verify"],
    "rate_limit": 100,
    "expires_in_days": 90
  }'
```

**Response**:

```json
{
  "api_key": "ak_abc123def456...",
  "key_id": "my-app-a1b2c3d4",
  "user_id": "admin",
  "scopes": ["verify"],
  "rate_limit": 100,
  "created_at": "2025-10-30T10:00:00Z",
  "expires_at": "2026-01-28T10:00:00Z"
}
```

**Use API Key**:

```bash
curl -X POST http://localhost:8888/verify \
  -H "X-API-Key: ak_abc123def456..." \
  -H "Content-Type: application/json" \
  -d @request.json
```

### Demo Users

For testing purposes, two demo users are available:

| Username | Password | Scopes | Access Level |
|----------|----------|--------|--------------|
| `admin` | `admin123` | `admin`, `verify` | Full access including API key management |
| `demo` | `demo123` | `verify` | Verification access only |

**⚠️ Change these credentials in production!**

### Scopes

| Scope | Description | Endpoints |
|-------|-------------|-----------|
| `verify` | Verification access | POST /verify, GET /statistics |
| `admin` | Administrative access | All endpoints including API key management |

### Token Refresh

Refresh an expiring JWT token without re-authentication:

```bash
curl -X POST http://localhost:8888/auth/refresh \
  -H "Authorization: Bearer <current-token>" \
  -H "Content-Type: application/json"
```

**Response**:

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

---

## Endpoints

### POST /verify

Verify an LLM-generated answer against source documents.

#### Request

**Method**: `POST`
**Path**: `/verify`
**Content-Type**: `application/json`

**Request Body**:

```json
{
  "answer": "Nach § 823 BGB haftet, wer vorsätzlich oder fahrlässig einen Schaden verursacht.",
  "sources": [
    {
      "text": "Wer vorsätzlich oder fahrlässig das Leben, den Körper, die Gesundheit, die Freiheit, das Eigentum oder ein sonstiges Recht eines anderen widerrechtlich verletzt, ist dem anderen zum Ersatz des daraus entstehenden Schadens verpflichtet.",
      "source_id": "bgb_823_abs1",
      "score": 0.95,
      "metadata": {
        "law": "BGB",
        "section": "823",
        "paragraph": "1"
      }
    },
    {
      "text": "Die gleiche Verpflichtung trifft denjenigen, welcher gegen ein den Schutz eines anderen bezweckendes Gesetz verstößt.",
      "source_id": "bgb_823_abs2",
      "score": 0.82,
      "metadata": {
        "law": "BGB",
        "section": "823",
        "paragraph": "2"
      }
    }
  ],
  "threshold": 0.75,
  "strict_mode": false,
  "config": {
    "language": "de",
    "domain": "legal",
    "enable_citations": true,
    "enable_retry": true
  }
}
```

**Parameters**:

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `answer` | string | Yes | - | The LLM-generated answer to verify |
| `sources` | array | Yes | - | Array of source documents (min: 1, max: 100) |
| `threshold` | number | No | 0.75 | Confidence threshold (0.0-1.0) |
| `strict_mode` | boolean | No | false | Enable strict verification mode |
| `config` | object | No | {} | Additional configuration options |

**Source Object**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `text` | string | Yes | Source document text |
| `source_id` | string | Yes | Unique identifier for the source |
| `score` | number | No | Retrieval score from RAG system (0.0-1.0) |
| `metadata` | object | No | Additional metadata (law, section, etc.) |

#### Response

**Status Code**: `200 OK` (on success)

**Response Body**:

```json
{
  "overall_confidence": 0.89,
  "trust_label": "Verified (High Confidence)",
  "overall_status": "verified",
  "sentence_results": [
    {
      "sentence": "Nach § 823 BGB haftet, wer vorsätzlich oder fahrlässig einen Schaden verursacht.",
      "confidence": 0.89,
      "status": "verified",
      "best_match": {
        "source_id": "bgb_823_abs1",
        "similarity": 0.94,
        "text_snippet": "Wer vorsätzlich oder fahrlässig das Leben, den Körper, die Gesundheit..."
      },
      "citations_found": ["§ 823 BGB"],
      "explanations": [
        "High semantic similarity (0.94) to source bgb_823_abs1",
        "Found legal citation: § 823 BGB",
        "Source retrieval score is high (0.95)"
      ],
      "warnings": []
    }
  ],
  "metadata": {
    "total_sentences": 1,
    "verified_count": 1,
    "review_count": 0,
    "rejected_count": 0,
    "processing_time_ms": 23.5,
    "model": "intfloat/multilingual-e5-large",
    "spacy_model": "de_core_news_md",
    "language": "de",
    "retry_count": 0
  },
  "fingerprints": [
    {
      "source_id": "bgb_823_abs1",
      "fingerprint": "a3f5c8d9e2b1...",
      "changed": false
    }
  ]
}
```

**Response Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `overall_confidence` | number | Overall confidence score (0.0-1.0) |
| `trust_label` | string | Human-readable trust label |
| `overall_status` | string | Overall status: `verified`, `review`, `rejected` |
| `sentence_results` | array | Per-sentence verification results |
| `metadata` | object | Processing metadata |
| `fingerprints` | array | Source fingerprints for change detection |

**Trust Labels**:

| Label | Confidence Range | Meaning |
|-------|-----------------|---------|
| `Verified (High Confidence)` | ≥ 0.90 | All claims strongly supported by sources |
| `Verified (Moderate Confidence)` | 0.80 - 0.89 | Claims reasonably supported by sources |
| `Review Required (Low Confidence)` | 0.60 - 0.79 | Some claims weakly supported, manual review needed |
| `Rejected (Very Low Confidence)` | < 0.60 | Claims not adequately supported by sources |

#### Examples

**Example 1: Simple Verification**

Request:

```bash
curl -X POST http://localhost:8888/verify \
  -H "Content-Type: application/json" \
  -d '{
    "answer": "Nach § 823 BGB haftet wer fahrlässig handelt.",
    "sources": [
      {
        "text": "Wer vorsätzlich oder fahrlässig einen Schaden verursacht, ist zum Ersatz verpflichtet.",
        "source_id": "bgb_823",
        "score": 0.95
      }
    ]
  }'
```

Response:

```json
{
  "overall_confidence": 0.87,
  "trust_label": "Verified (Moderate Confidence)",
  "overall_status": "verified",
  "sentence_results": [...],
  "metadata": {
    "processing_time_ms": 24.2,
    "total_sentences": 1
  }
}
```

**Example 2: Strict Mode**

Request:

```bash
curl -X POST http://localhost:8888/verify \
  -H "Content-Type: application/json" \
  -d '{
    "answer": "Die Haftung nach § 823 BGB ist verschuldensabhängig.",
    "sources": [...],
    "strict_mode": true,
    "threshold": 0.85
  }'
```

**Example 3: Multiple Sources**

Request:

```bash
curl -X POST http://localhost:8888/verify \
  -H "Content-Type: application/json" \
  -d '{
    "answer": "Nach § 823 BGB und Art. 1 GG gelten besondere Haftungsregeln.",
    "sources": [
      {"text": "...", "source_id": "bgb_823", "score": 0.95},
      {"text": "...", "source_id": "gg_art1", "score": 0.88}
    ]
  }'
```

---

### GET /health

Health check endpoint for monitoring and load balancers.

#### Request

**Method**: `GET`
**Path**: `/health`

No request body or parameters.

#### Response

**Status Code**: `200 OK` (healthy) or `503 Service Unavailable` (unhealthy)

**Response Body**:

```json
{
  "status": "healthy",
  "version": "0.1.0",
  "models": {
    "spacy": "de_core_news_md",
    "embedding": "intfloat/multilingual-e5-large"
  },
  "database": {
    "connected": true,
    "type": "postgresql"
  },
  "cache": {
    "enabled": true,
    "size": 342,
    "max_size": 1000
  }
}
```

**Response Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | `healthy` or `unhealthy` |
| `version` | string | API version |
| `models` | object | Loaded model information |
| `database` | object | Database connection status |
| `cache` | object | Cache statistics |

#### Example

```bash
curl http://localhost:8888/health

# Output:
# {"status":"healthy","version":"0.1.0",...}
```

**Use Cases:**

- Docker health checks
- Kubernetes liveness probes
- Load balancer health checks
- Monitoring systems

---

### GET /metrics

Prometheus metrics endpoint for monitoring.

#### Request

**Method**: `GET`
**Path**: `/metrics`

No request body or parameters.

#### Response

**Status Code**: `200 OK`
**Content-Type**: `text/plain; version=0.0.4; charset=utf-8`

**Response Body** (Prometheus format):

```
# HELP auditor_verify_requests_total Total verification requests
# TYPE auditor_verify_requests_total counter
auditor_verify_requests_total{status="success",trust_label="Verified (High Confidence)"} 1523.0
auditor_verify_requests_total{status="success",trust_label="Verified (Moderate Confidence)"} 842.0
auditor_verify_requests_total{status="success",trust_label="Review Required (Low Confidence)"} 231.0
auditor_verify_requests_total{status="error"} 12.0

# HELP auditor_verify_latency_seconds Verification request latency
# TYPE auditor_verify_latency_seconds histogram
auditor_verify_latency_seconds_bucket{le="0.01"} 142.0
auditor_verify_latency_seconds_bucket{le="0.05"} 1401.0
auditor_verify_latency_seconds_bucket{le="0.1"} 2234.0
auditor_verify_latency_seconds_bucket{le="0.5"} 2589.0
auditor_verify_latency_seconds_bucket{le="1.0"} 2605.0
auditor_verify_latency_seconds_bucket{le="+Inf"} 2608.0
auditor_verify_latency_seconds_sum 58.234
auditor_verify_latency_seconds_count 2608.0

# HELP auditor_confidence_score Confidence score distribution
# TYPE auditor_confidence_score histogram
auditor_confidence_score_bucket{le="0.5"} 45.0
auditor_confidence_score_bucket{le="0.6"} 123.0
auditor_confidence_score_bucket{le="0.7"} 312.0
auditor_confidence_score_bucket{le="0.8"} 756.0
auditor_confidence_score_bucket{le="0.9"} 1823.0
auditor_confidence_score_bucket{le="1.0"} 2608.0
auditor_confidence_score_sum 2234.56
auditor_confidence_score_count 2608.0

# HELP auditor_cache_hits_total Embedding cache hits
# TYPE auditor_cache_hits_total counter
auditor_cache_hits_total 1845.0

# HELP auditor_cache_misses_total Embedding cache misses
# TYPE auditor_cache_misses_total counter
auditor_cache_misses_total 763.0
```

**Available Metrics**:

| Metric | Type | Description |
|--------|------|-------------|
| `auditor_verify_requests_total` | Counter | Total verification requests |
| `auditor_verify_latency_seconds` | Histogram | Request latency distribution |
| `auditor_verify_in_progress` | Gauge | Active verification requests |
| `auditor_confidence_score` | Histogram | Confidence score distribution |
| `auditor_sources_processed_total` | Counter | Total sources processed |
| `auditor_citations_extracted_total` | Counter | Total citations extracted |
| `auditor_cache_hits_total` | Counter | Embedding cache hits |
| `auditor_cache_misses_total` | Counter | Embedding cache misses |

#### Example

```bash
curl http://localhost:8888/metrics

# Scrape with Prometheus
# See docs/MONITORING.md for Prometheus configuration
```

---

### GET /docs

Interactive API documentation (Swagger UI).

#### Request

**Method**: `GET`
**Path**: `/docs`

Access via browser.

#### Response

**Status Code**: `200 OK`
**Content-Type**: `text/html`

Returns interactive Swagger UI with:

- All endpoint descriptions
- Request/response schemas
- Try-it-out functionality
- Example requests

#### Example

```bash
# Open in browser
open http://localhost:8888/docs

# Alternative: ReDoc
open http://localhost:8888/redoc
```

---

### POST /auth/login

Login with username and password to obtain a JWT token.

#### Request

**Method**: `POST`
**Path**: `/auth/login`
**Content-Type**: `application/json`
**Authentication**: None required

**Request Body**:

```json
{
  "username": "admin",
  "password": "admin123"
}
```

**Parameters**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `username` | string | Yes | Username (3-50 characters) |
| `password` | string | Yes | Password (minimum 8 characters) |

#### Response

**Status Code**: `200 OK` (on success), `401 Unauthorized` (on failure)

**Response Body**:

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJhZG1pbiIsInNjb3BlcyI6WyJhZG1pbiIsInZlcmlmeSJdLCJleHAiOjE2OTg3NjcyOTIsImlhdCI6MTY5ODc2NTQ5Mn0.abc123...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

**Response Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `access_token` | string | JWT token for authentication |
| `token_type` | string | Always "bearer" |
| `expires_in` | integer | Token lifetime in seconds |

#### Example

```bash
curl -X POST http://localhost:8888/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'
```

---

### POST /auth/refresh

Refresh an expiring JWT token.

#### Request

**Method**: `POST`
**Path**: `/auth/refresh`
**Content-Type**: `application/json`
**Authentication**: JWT Bearer token required

**Headers**:

```
Authorization: Bearer <current-token>
```

No request body.

#### Response

**Status Code**: `200 OK` (on success), `401 Unauthorized` (on failure)

**Response Body**:

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

#### Example

```bash
curl -X POST http://localhost:8888/auth/refresh \
  -H "Authorization: Bearer <your-token>"
```

---

### POST /auth/api-keys

Create a new API key for programmatic access.

#### Request

**Method**: `POST`
**Path**: `/auth/api-keys`
**Content-Type**: `application/json`
**Authentication**: JWT Bearer token with `admin` scope required

**Request Body**:

```json
{
  "name": "my-production-app",
  "scopes": ["verify"],
  "rate_limit": 100,
  "expires_in_days": 90
}
```

**Parameters**:

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `name` | string | Yes | - | Descriptive name for the API key (1-100 chars) |
| `scopes` | array | Yes | - | List of scopes: `verify`, `admin` |
| `rate_limit` | integer | No | 60 | Custom rate limit (requests/minute) |
| `expires_in_days` | integer | No | 365 | Days until expiration (1-3650) |

#### Response

**Status Code**: `201 Created` (on success), `401 Unauthorized` (on auth failure), `403 Forbidden` (missing admin scope)

**Response Body**:

```json
{
  "api_key": "ak_1a2b3c4d5e6f7g8h9i0j...",
  "key_id": "my-production-app-a1b2c3d4",
  "user_id": "admin",
  "scopes": ["verify"],
  "rate_limit": 100,
  "created_at": "2025-10-30T10:00:00Z",
  "expires_at": "2026-01-28T10:00:00Z"
}
```

**⚠️ Important**: The `api_key` value is only shown once. Store it securely.

**Response Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `api_key` | string | The API key (shown only once) |
| `key_id` | string | Unique identifier for this key |
| `user_id` | string | Owner of the API key |
| `scopes` | array | Granted scopes |
| `rate_limit` | integer | Requests per minute allowed |
| `created_at` | string | ISO 8601 creation timestamp |
| `expires_at` | string | ISO 8601 expiration timestamp |

#### Example

```bash
curl -X POST http://localhost:8888/auth/api-keys \
  -H "Authorization: Bearer <admin-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "my-app",
    "scopes": ["verify"],
    "rate_limit": 100,
    "expires_in_days": 90
  }'
```

---

### GET /auth/api-keys

List all API keys for the current user.

#### Request

**Method**: `GET`
**Path**: `/auth/api-keys`
**Authentication**: JWT Bearer token required

**Headers**:

```
Authorization: Bearer <your-token>
```

No request body or parameters.

#### Response

**Status Code**: `200 OK`

**Response Body**:

```json
{
  "api_keys": [
    {
      "key_id": "my-app-a1b2c3d4",
      "name": "my-app",
      "scopes": ["verify"],
      "rate_limit": 100,
      "created_at": "2025-10-30T10:00:00Z",
      "expires_at": "2026-01-28T10:00:00Z",
      "last_used_at": "2025-10-30T12:34:56Z"
    },
    {
      "key_id": "backup-key-x9y8z7",
      "name": "backup-key",
      "scopes": ["verify"],
      "rate_limit": 60,
      "created_at": "2025-09-15T08:00:00Z",
      "expires_at": "2026-09-15T08:00:00Z",
      "last_used_at": null
    }
  ]
}
```

**Note**: The actual `api_key` value is never returned (only `key_id`).

#### Example

```bash
curl -X GET http://localhost:8888/auth/api-keys \
  -H "Authorization: Bearer <your-token>"
```

---

### DELETE /auth/api-keys/{key_id}

Revoke an API key.

#### Request

**Method**: `DELETE`
**Path**: `/auth/api-keys/{key_id}`
**Authentication**: JWT Bearer token required (must own the key or have `admin` scope)

**Path Parameters**:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `key_id` | string | Yes | The key ID to revoke |

**Headers**:

```
Authorization: Bearer <your-token>
```

No request body.

#### Response

**Status Code**: `200 OK` (on success), `404 Not Found` (key not found), `403 Forbidden` (not authorized)

**Response Body**:

```json
{
  "message": "API key revoked successfully",
  "key_id": "my-app-a1b2c3d4"
}
```

#### Example

```bash
curl -X DELETE http://localhost:8888/auth/api-keys/my-app-a1b2c3d4 \
  -H "Authorization: Bearer <your-token>"
```

---

### GET /auth/me

Get information about the current authenticated user.

#### Request

**Method**: `GET`
**Path**: `/auth/me`
**Authentication**: JWT Bearer token or API key required

**Headers** (choose one):

```
Authorization: Bearer <jwt-token>
```

or

```
X-API-Key: <api-key>
```

No request body or parameters.

#### Response

**Status Code**: `200 OK` (on success), `401 Unauthorized` (not authenticated)

**Response Body** (JWT):

```json
{
  "auth_type": "jwt",
  "user_id": "admin",
  "scopes": ["admin", "verify"],
  "token_expires_at": "2025-10-30T11:00:00Z"
}
```

**Response Body** (API Key):

```json
{
  "auth_type": "api_key",
  "user_id": "admin",
  "scopes": ["verify"],
  "key_id": "my-app-a1b2c3d4",
  "rate_limit": 100,
  "expires_at": "2026-01-28T10:00:00Z"
}
```

**Response Fields**:

| Field | Type | Description |
|-------|------|-------------|
| `auth_type` | string | Authentication method: `jwt` or `api_key` |
| `user_id` | string | User identifier |
| `scopes` | array | Granted scopes |
| `token_expires_at` | string | JWT expiration (JWT only) |
| `key_id` | string | API key identifier (API key only) |
| `rate_limit` | integer | Rate limit (API key only) |
| `expires_at` | string | API key expiration (API key only) |

#### Example

```bash
# With JWT
curl -X GET http://localhost:8888/auth/me \
  -H "Authorization: Bearer <jwt-token>"

# With API Key
curl -X GET http://localhost:8888/auth/me \
  -H "X-API-Key: <api-key>"
```

---

## Request Models

### VerificationRequest

Complete request model for `/verify` endpoint.

```python
class VerificationRequest(BaseModel):
    answer: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="The LLM-generated answer to verify"
    )
    sources: List[Source] = Field(
        ...,
        min_items=1,
        max_items=100,
        description="Source documents for verification"
    )
    threshold: float = Field(
        0.75,
        ge=0.0,
        le=1.0,
        description="Confidence threshold for verification"
    )
    strict_mode: bool = Field(
        False,
        description="Enable strict verification mode"
    )
    config: Optional[Config] = Field(
        None,
        description="Additional configuration options"
    )
```

**Validation Rules**:

- `answer`: 1-10,000 characters
- `sources`: 1-100 sources
- `threshold`: 0.0-1.0 (inclusive)
- `strict_mode`: boolean
- `config`: optional configuration object

### Source

Source document model.

```python
class Source(BaseModel):
    text: str = Field(
        ...,
        min_length=1,
        max_length=50000,
        description="Source document text"
    )
    source_id: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Unique identifier for the source"
    )
    score: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Retrieval score from RAG system"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional metadata"
    )
```

**Validation Rules**:

- `text`: 1-50,000 characters
- `source_id`: 1-255 characters, unique
- `score`: 0.0-1.0 (optional)
- `metadata`: arbitrary JSON object (optional)

### Config

Optional configuration model.

```python
class Config(BaseModel):
    language: str = Field("de", description="Language code (ISO 639-1)")
    domain: str = Field("legal", description="Domain (legal, medical, etc.)")
    enable_citations: bool = Field(True, description="Extract citations")
    enable_retry: bool = Field(True, description="Auto-retry on low confidence")
    max_retries: int = Field(2, ge=0, le=5, description="Max retry attempts")
```

---

## Response Models

### VerificationResponse

Complete response model for `/verify` endpoint.

```python
class VerificationResponse(BaseModel):
    overall_confidence: float
    trust_label: str
    overall_status: str  # "verified", "review", "rejected"
    sentence_results: List[SentenceResult]
    metadata: Metadata
    fingerprints: List[Fingerprint]
```

### SentenceResult

Per-sentence verification result.

```python
class SentenceResult(BaseModel):
    sentence: str
    confidence: float
    status: str  # "verified", "review", "rejected"
    best_match: Optional[Match]
    citations_found: List[str]
    explanations: List[str]
    warnings: List[str]
```

### Match

Best matching source for a sentence.

```python
class Match(BaseModel):
    source_id: str
    similarity: float
    text_snippet: str  # First 100 characters
```

### Metadata

Processing metadata.

```python
class Metadata(BaseModel):
    total_sentences: int
    verified_count: int
    review_count: int
    rejected_count: int
    processing_time_ms: float
    model: str
    spacy_model: str
    language: str
    retry_count: int
```

### Fingerprint

Source fingerprint for change detection.

```python
class Fingerprint(BaseModel):
    source_id: str
    fingerprint: str  # SHA-256 hash
    changed: bool
```

---

## Error Handling

### Error Response Format

All errors return a consistent JSON format:

```json
{
  "detail": "Error message describing what went wrong",
  "error_code": "VALIDATION_ERROR",
  "status_code": 422
}
```

### HTTP Status Codes

| Code | Meaning | When |
|------|---------|------|
| `200` | OK | Successful verification |
| `400` | Bad Request | Invalid request parameters |
| `422` | Unprocessable Entity | Validation error |
| `429` | Too Many Requests | Rate limit exceeded (v1.1) |
| `500` | Internal Server Error | Server-side error |
| `503` | Service Unavailable | Service unhealthy |

### Error Codes

| Code | Description | Resolution |
|------|-------------|------------|
| `VALIDATION_ERROR` | Request validation failed | Check request parameters |
| `MISSING_FIELD` | Required field missing | Provide all required fields |
| `INVALID_THRESHOLD` | Threshold out of range | Use 0.0-1.0 |
| `TOO_MANY_SOURCES` | Sources exceed limit | Reduce to ≤100 sources |
| `MODEL_ERROR` | Model loading/inference failed | Check server logs |
| `DATABASE_ERROR` | Database operation failed | Check database connection |

### Example Error Responses

**Validation Error (422)**:

```json
{
  "detail": [
    {
      "loc": ["body", "threshold"],
      "msg": "ensure this value is less than or equal to 1.0",
      "type": "value_error.number.not_le"
    }
  ]
}
```

**Server Error (500)**:

```json
{
  "detail": "Internal server error occurred during verification",
  "error_code": "MODEL_ERROR"
}
```

**Rate Limit Error (429)** (v1.1):

```json
{
  "detail": "Rate limit exceeded: 100 requests per minute",
  "error_code": "RATE_LIMIT_EXCEEDED",
  "retry_after": 23
}
```

---

## Rate Limiting

### Overview

Rate limiting is **optional** and **disabled by default**. Enable it in production to protect against abuse and ensure fair resource allocation.

The rate limiter uses a **sliding window algorithm** with burst protection for accurate request tracking.

### Configuration

**Enable Rate Limiting** (`.env`):

```bash
ENABLE_RATE_LIMITING=true
RATE_LIMIT_PER_MINUTE=60
RATE_LIMIT_BURST=10
```

**Default**: Rate limiting is disabled for development and backward compatibility.

### Default Limits

When enabled:

- **Per-minute limit**: 60 requests per minute per client
- **Burst limit**: 10 requests per second
- **Window size**: 60 seconds (sliding window)
- **Client identification**: IP address or API key

### Custom Limits

API keys can have **custom rate limits** set at creation:

```bash
curl -X POST http://localhost:8888/auth/api-keys \
  -H "Authorization: Bearer <admin-token>" \
  -d '{"name": "high-volume-app", "rate_limit": 500, ...}'
```

This API key will have a 500 requests/minute limit instead of the default 60.

### Rate Limit Headers

Every response includes rate limit information:

```
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 42
X-RateLimit-Reset: 1698765492
```

**Headers**:

| Header | Description | Example |
|--------|-------------|---------|
| `X-RateLimit-Limit` | Maximum requests per minute | `60` |
| `X-RateLimit-Remaining` | Requests remaining in current window | `42` |
| `X-RateLimit-Reset` | Unix timestamp when limit resets | `1698765492` |

### Exceeding Limits

When the rate limit is exceeded, the API returns `429 Too Many Requests`:

**Response** (HTTP 429):

```json
{
  "detail": "Rate limit exceeded. Please try again later."
}
```

**Headers**:

```
HTTP/1.1 429 Too Many Requests
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 0
X-RateLimit-Reset: 1698765522
Retry-After: 30
```

The `Retry-After` header indicates how many seconds to wait before retrying.

### Burst Protection

The rate limiter includes burst protection to prevent rapid-fire requests:

- **Burst limit**: 10 requests per second
- **Detection**: Tracks requests within 1-second windows
- **Response**: Returns `429` with `Retry-After: 1` when burst limit exceeded

**Example**:

```bash
# Request 1-10 (within 1 second) → ✅ Allowed
# Request 11 (within same second) → ❌ 429 Too Many Requests, Retry-After: 1
```

### Rate Limit Tracking

Rate limits are tracked per:

1. **IP Address** - For unauthenticated requests
2. **API Key** - For authenticated requests with API keys
3. **User ID** - For authenticated requests with JWT tokens

Each client is tracked independently with isolated rate limit counters.

### Algorithm: Sliding Window

The rate limiter uses a **sliding window** algorithm for accurate tracking:

- **Advantage**: No edge-case burst at window boundaries
- **Implementation**: Tracks individual request timestamps
- **Cleanup**: Automatically removes expired timestamps

**Example**:

```
Time:    10:00:00  10:00:30  10:01:00  10:01:30
Limit:   60 req/min
Window:  [←─────── 60 seconds ─────────→]

At 10:01:30, only requests after 10:00:30 count toward the limit.
```

### Best Practices

**Client Implementation**:

```python
import requests
import time

def call_api_with_retry(url, data):
    while True:
        response = requests.post(url, json=data)

        if response.status_code == 200:
            return response.json()

        elif response.status_code == 429:
            retry_after = int(response.headers.get('Retry-After', 60))
            print(f"Rate limited, waiting {retry_after} seconds...")
            time.sleep(retry_after)

        else:
            response.raise_for_status()
```

**Recommendations**:

1. **Check headers**: Monitor `X-RateLimit-Remaining` to avoid hitting limits
2. **Respect Retry-After**: Always wait the specified time before retrying
3. **Exponential backoff**: Implement exponential backoff for repeated 429s
4. **Use API keys**: API keys can have custom higher limits
5. **Batch requests**: Combine multiple verifications when possible

### Monitoring

Track rate limiting metrics via Prometheus:

```
# Rate limit hits
auditor_rate_limit_exceeded_total{client="192.168.1.1"} 5

# Rate limit checks
auditor_rate_limit_checks_total{result="allowed"} 1523
auditor_rate_limit_checks_total{result="blocked"} 45
```

See [MONITORING.md](MONITORING.md) for full metrics documentation

---

## Security Headers

### Overview

The API automatically applies security headers to all responses to protect against common web vulnerabilities. These headers are always enabled and comply with **OWASP Top 10** security best practices.

### Applied Headers

| Header | Value | Purpose |
|--------|-------|---------|
| `X-Frame-Options` | `DENY` | Prevent clickjacking attacks |
| `X-Content-Type-Options` | `nosniff` | Prevent MIME type sniffing |
| `X-XSS-Protection` | `1; mode=block` | Enable browser XSS protection |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Control referrer information |
| `Permissions-Policy` | `camera=(), microphone=(), ...` | Restrict browser features |
| `Content-Security-Policy` | `default-src 'self'; ...` | Prevent XSS and injection attacks |
| `Strict-Transport-Security` | `max-age=31536000` (production only) | Enforce HTTPS |

### Content Security Policy (CSP)

The API uses a strict Content Security Policy to prevent XSS attacks:

```
Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'
```

**Directives**:

- `default-src 'self'` - Only load resources from same origin
- `script-src 'self'` - Only execute scripts from same origin
- `style-src 'self' 'unsafe-inline'` - Allow inline styles for Swagger UI
- `frame-ancestors 'none'` - Prevent embedding in iframes
- `form-action 'self'` - Only submit forms to same origin

### Permissions Policy

The API restricts access to sensitive browser features:

```
Permissions-Policy: camera=(), microphone=(), geolocation=(), interest-cohort=(), payment=(), usb=()
```

This prevents the API from accessing:

- Camera and microphone
- Geolocation
- Payment handlers
- USB devices
- FLoC (privacy protection)

### HSTS (HTTP Strict Transport Security)

In **production** environments (`ENVIRONMENT=production`), HSTS is enabled:

```
Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
```

**Configuration**:

- **max-age**: 1 year (31536000 seconds)
- **includeSubDomains**: Apply to all subdomains
- **preload**: Eligible for browser HSTS preload list

⚠️ **Note**: HSTS is **disabled** in development to allow HTTP testing.

### CORS (Cross-Origin Resource Sharing)

CORS is configured based on environment:

**Development** (default):

```
Access-Control-Allow-Origin: *
Access-Control-Allow-Methods: GET, POST
Access-Control-Allow-Headers: Content-Type, Authorization, X-API-Key
Access-Control-Allow-Credentials: true
Access-Control-Expose-Headers: X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset
```

**Production** (configured via environment):

```bash
# .env
CORS_ORIGINS=https://app.example.com,https://dashboard.example.com
CORS_METHODS=GET,POST
CORS_HEADERS=Content-Type,Authorization,X-API-Key
```

**Exposed Headers**: Rate limit headers are always exposed for client monitoring:

- `X-RateLimit-Limit`
- `X-RateLimit-Remaining`
- `X-RateLimit-Reset`

### Security Best Practices

**Production Checklist**:

1. ✅ **Enable HTTPS** - Always use TLS in production
2. ✅ **Configure CORS** - Set specific allowed origins
3. ✅ **Enable authentication** - Require API keys or JWT tokens
4. ✅ **Enable rate limiting** - Protect against abuse
5. ✅ **Set strong JWT secret** - Use 32+ character random key
6. ✅ **Monitor security headers** - Verify headers in responses
7. ✅ **Review CSP** - Adjust if needed for your frontend

**Verify Security Headers**:

```bash
curl -I http://localhost:8888/health

# Output should include:
# X-Frame-Options: DENY
# X-Content-Type-Options: nosniff
# Content-Security-Policy: default-src 'self'; ...
# Permissions-Policy: camera=(), microphone=(), ...
```

### OWASP Top 10 Compliance

The security headers address these OWASP Top 10 vulnerabilities:

| OWASP | Vulnerability | Mitigation |
|-------|---------------|------------|
| A01:2021 | Broken Access Control | Authentication + authorization required |
| A02:2021 | Cryptographic Failures | Bcrypt password hashing, JWT signing |
| A03:2021 | Injection | CSP, input validation (Pydantic) |
| A04:2021 | Insecure Design | Security by default, opt-in features |
| A05:2021 | Security Misconfiguration | Secure headers, environment-based config |
| A06:2021 | Vulnerable Components | Regular dependency updates |
| A07:2021 | Authentication Failures | JWT expiration, API key hashing |
| A08:2021 | Data Integrity Failures | HSTS in production |
| A09:2021 | Logging Failures | Comprehensive audit logging |
| A10:2021 | SSRF | CSP, restricted network access |

---

## Examples

### Python Client

```python
import requests

# Verification request
response = requests.post(
    "http://localhost:8888/verify",
    json={
        "answer": "Nach § 823 BGB haftet wer fahrlässig handelt.",
        "sources": [
            {
                "text": "Wer vorsätzlich oder fahrlässig...",
                "source_id": "bgb_823",
                "score": 0.95
            }
        ],
        "threshold": 0.75
    }
)

result = response.json()
print(f"Confidence: {result['overall_confidence']}")
print(f"Trust Label: {result['trust_label']}")
```

### cURL

```bash
# Verification
curl -X POST http://localhost:8888/verify \
  -H "Content-Type: application/json" \
  -d @- <<EOF
{
  "answer": "Nach § 823 BGB haftet wer fahrlässig handelt.",
  "sources": [
    {
      "text": "Wer vorsätzlich oder fahrlässig...",
      "source_id": "bgb_823",
      "score": 0.95
    }
  ]
}
EOF

# Health check
curl http://localhost:8888/health

# Metrics
curl http://localhost:8888/metrics
```

### JavaScript (Node.js)

```javascript
const axios = require('axios');

async function verifyAnswer(answer, sources) {
  try {
    const response = await axios.post('http://localhost:8888/verify', {
      answer,
      sources,
      threshold: 0.75
    });

    console.log('Confidence:', response.data.overall_confidence);
    console.log('Trust Label:', response.data.trust_label);

    return response.data;
  } catch (error) {
    console.error('Verification failed:', error.response.data);
    throw error;
  }
}

// Usage
verifyAnswer(
  "Nach § 823 BGB haftet wer fahrlässig handelt.",
  [
    {
      text: "Wer vorsätzlich oder fahrlässig...",
      source_id: "bgb_823",
      score: 0.95
    }
  ]
);
```

### Java (Spring RestTemplate)

```java
import org.springframework.web.client.RestTemplate;
import org.springframework.http.*;

public class AuditorClient {
    private final RestTemplate restTemplate = new RestTemplate();
    private final String baseUrl = "http://localhost:8888";

    public VerificationResponse verify(VerificationRequest request) {
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);

        HttpEntity<VerificationRequest> entity =
            new HttpEntity<>(request, headers);

        ResponseEntity<VerificationResponse> response =
            restTemplate.exchange(
                baseUrl + "/verify",
                HttpMethod.POST,
                entity,
                VerificationResponse.class
            );

        return response.getBody();
    }
}
```

---

## Client Libraries

### Official Libraries (Planned)

- Python: `pip install juragpt-auditor-client`
- JavaScript: `npm install @juragpt/auditor-client`
- Java: Maven/Gradle package

### Community Libraries

Submit PRs to add your client library!

---

## Versioning

### API Versioning Strategy

**Current**: v0.1.0 (no version in URL)

**Future** (v2.0+): Versioning via URL path

```
https://api.juragpt.example.com/v2/verify
```

**Backward Compatibility**:

- v1.x: Backward compatible changes only
- v2.x: Breaking changes allowed

### Changelog

See [CHANGELOG.md](../CHANGELOG.md) for version history.

---

## Support

- **Documentation**: [docs/](.)
- **Issues**: [GitHub Issues](https://github.com/yourusername/auditor/issues)
- **API Questions**: [GitHub Discussions](https://github.com/yourusername/auditor/discussions)

---

## Additional Resources

- [Architecture Documentation](ARCHITECTURE.md)
- [Deployment Guide](DEPLOYMENT.md)
- [Monitoring Guide](MONITORING.md)
- [Configuration Reference](CONFIGURATION.md)

---

**Built with ❤️ by the JuraGPT Team**
