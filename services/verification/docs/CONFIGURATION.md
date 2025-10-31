# Configuration Reference

This document provides a comprehensive reference for all configuration options available in JuraGPT Auditor.

## Table of Contents

- [Configuration Overview](#configuration-overview)
- [Environment Variables](#environment-variables)
- [Configuration File (config.yaml)](#configuration-file-configyaml)
- [Database Configuration](#database-configuration)
- [API Configuration](#api-configuration)
- [NLP Model Configuration](#nlp-model-configuration)
- [Processing Configuration](#processing-configuration)
- [Logging Configuration](#logging-configuration)
- [Monitoring Configuration](#monitoring-configuration)
- [Security Configuration](#security-configuration)
- [Performance Tuning](#performance-tuning)
- [Feature Flags](#feature-flags)
- [Docker Configuration](#docker-configuration)
- [Kubernetes Configuration](#kubernetes-configuration)
- [Configuration Validation](#configuration-validation)
- [Examples](#examples)

## Configuration Overview

JuraGPT Auditor can be configured through multiple methods, with the following precedence (highest to lowest):

1. **Environment variables** (highest priority)
2. **Configuration file** (`config.yaml`)
3. **Default values** (lowest priority)

### Configuration Loading

```python
# Configuration is loaded automatically on startup
from auditor.config.settings import get_settings

settings = get_settings()

# Settings are cached and validated using Pydantic
```

### Configuration Files

**Primary configuration file**: `.env` (environment variables)
**Optional YAML config**: `config.yaml` (structured configuration)
**Example files**:
- `.env.example` - Environment variable template
- `config.example.yaml` - YAML configuration template

## Environment Variables

### Required Variables

These variables must be set for the application to run:

```bash
# Database connection string
DATABASE_URL=postgresql://user:password@host:port/database
# Example: postgresql://auditor:auditor_password@localhost:5432/auditor
```

### Optional Variables

#### API Configuration

```bash
# API server host (default: 0.0.0.0)
API_HOST=0.0.0.0

# API server port (default: 8000)
API_PORT=8000

# API root path (for reverse proxies)
API_ROOT_PATH=/api/v1

# CORS allowed origins (comma-separated)
CORS_ORIGINS=http://localhost:3000,https://app.example.com

# CORS allowed methods (comma-separated)
CORS_METHODS=GET,POST,PUT,DELETE

# CORS allowed headers (comma-separated)
CORS_HEADERS=Content-Type,Authorization

# CORS allow credentials (default: false)
CORS_ALLOW_CREDENTIALS=true
```

#### Logging Configuration

```bash
# Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL (default: INFO)
LOG_LEVEL=INFO

# Log format: json, text (default: json)
LOG_FORMAT=json

# Log output: stdout, file, both (default: stdout)
LOG_OUTPUT=stdout

# Log file path (if LOG_OUTPUT=file or both)
LOG_FILE=/var/log/auditor/app.log

# Enable access logs (default: true)
ENABLE_ACCESS_LOGS=true

# Enable SQL query logs (default: false, only for debugging)
ENABLE_SQL_LOGS=false
```

#### NLP Model Configuration

```bash
# spaCy model name (default: de_core_news_lg)
SPACY_MODEL=de_core_news_lg
# Alternatives: de_core_news_sm, de_core_news_md

# Sentence transformer model (default: paraphrase-multilingual-mpnet-base-v2)
EMBEDDING_MODEL=paraphrase-multilingual-mpnet-base-v2
# Alternatives:
#   - paraphrase-multilingual-MiniLM-L12-v2 (faster, less accurate)
#   - sentence-transformers/distiluse-base-multilingual-cased-v2

# Model cache directory (default: ~/.cache/huggingface)
MODEL_CACHE_DIR=/app/models

# Enable model caching (default: true)
ENABLE_MODEL_CACHE=true

# Embedding batch size (default: 32)
EMBEDDING_BATCH_SIZE=32

# GPU device ID (-1 for CPU, 0+ for GPU)
CUDA_DEVICE=-1
```

#### Processing Configuration

```bash
# Default confidence threshold (0.0 to 1.0, default: 0.75)
DEFAULT_THRESHOLD=0.75

# Maximum sources per verification request (default: 100)
MAX_SOURCES_PER_REQUEST=100

# Maximum answer length in characters (default: 10000)
MAX_ANSWER_LENGTH=10000

# Maximum source text length in characters (default: 50000)
MAX_SOURCE_LENGTH=50000

# Sentence segmentation language (default: de)
SENTENCE_LANGUAGE=de

# Minimum sentence length in characters (default: 10)
MIN_SENTENCE_LENGTH=10

# Semantic similarity threshold (0.0 to 1.0, default: 0.6)
SEMANTIC_THRESHOLD=0.6

# Citation matching confidence boost (default: 0.1)
CITATION_BOOST=0.1

# Source score weight in overall confidence (default: 0.2)
SOURCE_SCORE_WEIGHT=0.2

# Semantic score weight in overall confidence (default: 0.5)
SEMANTIC_SCORE_WEIGHT=0.5

# Citation score weight in overall confidence (default: 0.3)
CITATION_SCORE_WEIGHT=0.3
```

#### Database Configuration

```bash
# Database connection pool size (default: 5)
DB_POOL_SIZE=5

# Database max overflow connections (default: 10)
DB_MAX_OVERFLOW=10

# Database pool recycle time in seconds (default: 3600)
DB_POOL_RECYCLE=3600

# Database pool timeout in seconds (default: 30)
DB_POOL_TIMEOUT=30

# Database connection timeout in seconds (default: 10)
DB_CONNECT_TIMEOUT=10

# Enable database query logging (default: false)
DB_ECHO=false

# Database SSL mode: disable, allow, prefer, require (default: prefer)
DB_SSL_MODE=prefer

# Database SSL root certificate path
DB_SSL_ROOT_CERT=/path/to/ca-cert.pem
```

#### Monitoring Configuration

```bash
# Enable Prometheus metrics endpoint (default: true)
ENABLE_METRICS=true

# Prometheus metrics path (default: /metrics)
METRICS_PATH=/metrics

# Enable health check endpoint (default: true)
ENABLE_HEALTH_CHECK=true

# Health check path (default: /health)
HEALTH_CHECK_PATH=/health

# Prometheus pushgateway URL (optional)
PROMETHEUS_PUSHGATEWAY=http://pushgateway:9091

# Application name for metrics (default: auditor)
APP_NAME=auditor

# Application version (auto-detected from package)
APP_VERSION=1.0.0
```

#### Feature Flags

```bash
# Enable source fingerprinting (default: true)
ENABLE_FINGERPRINTING=true

# Enable request validation (default: true)
ENABLE_REQUEST_VALIDATION=true

# Enable response compression (default: true)
ENABLE_COMPRESSION=true

# Enable API documentation (default: true)
ENABLE_DOCS=true

# Enable OpenAPI schema endpoint (default: true)
ENABLE_OPENAPI=true

# Enable experimental features (default: false)
ENABLE_EXPERIMENTAL=false
```

#### Security Configuration

```bash
# Enable authentication (default: false)
ENABLE_AUTH=false

# JWT secret key (REQUIRED if ENABLE_AUTH=true, min 32 characters)
JWT_SECRET_KEY=your-secret-key-min-32-chars-change-in-production

# JWT signing algorithm (default: HS256)
JWT_ALGORITHM=HS256

# JWT access token expiration in minutes (default: 30)
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30

# Enable rate limiting (default: false)
ENABLE_RATE_LIMITING=false

# Rate limit: requests per minute (default: 60)
RATE_LIMIT_PER_MINUTE=60

# Rate limit: burst protection requests per second (default: 10)
RATE_LIMIT_BURST=10

# CORS allowed origins (comma-separated, default: * in development)
CORS_ORIGINS=https://app.example.com,https://dashboard.example.com

# CORS allowed methods (comma-separated, default: GET,POST)
CORS_METHODS=GET,POST

# CORS allowed headers (comma-separated)
CORS_HEADERS=Content-Type,Authorization,X-API-Key

# CORS allow credentials (default: true)
CORS_ALLOW_CREDENTIALS=true

# Environment: development, staging, production (default: development)
# Affects HSTS, CORS, error details, etc.
ENVIRONMENT=development

# Trusted proxy IPs (comma-separated, for X-Forwarded-For)
TRUSTED_PROXIES=127.0.0.1,10.0.0.0/8
```

#### Performance Configuration

```bash
# Number of worker processes (default: auto-detected)
WORKER_COUNT=4

# Worker class: uvicorn.workers.UvicornWorker (default)
WORKER_CLASS=uvicorn.workers.UvicornWorker

# Request timeout in seconds (default: 60)
REQUEST_TIMEOUT=60

# Keep-alive timeout in seconds (default: 5)
KEEP_ALIVE=5

# Maximum concurrent requests (default: 1000)
MAX_CONCURRENT_REQUESTS=1000

# Enable request queueing (default: true)
ENABLE_REQUEST_QUEUE=true

# Request queue size (default: 100)
REQUEST_QUEUE_SIZE=100
```

## Configuration File (config.yaml)

For complex configurations, you can use a YAML file:

```yaml
# config.yaml
api:
  host: 0.0.0.0
  port: 8000
  root_path: /api/v1
  cors:
    origins:
      - http://localhost:3000
      - https://app.example.com
    methods:
      - GET
      - POST
    allow_credentials: true

database:
  url: postgresql://auditor:password@localhost:5432/auditor
  pool:
    size: 5
    max_overflow: 10
    recycle: 3600
    timeout: 30
  ssl:
    mode: prefer
    root_cert: /path/to/ca-cert.pem

logging:
  level: INFO
  format: json
  output: stdout
  access_logs: true
  sql_logs: false

models:
  spacy: de_core_news_lg
  embedding: paraphrase-multilingual-mpnet-base-v2
  cache_dir: /app/models
  embedding_batch_size: 32
  cuda_device: -1

processing:
  default_threshold: 0.75
  max_sources: 100
  max_answer_length: 10000
  max_source_length: 50000
  min_sentence_length: 10
  semantic_threshold: 0.6
  weights:
    semantic: 0.5
    citation: 0.3
    source: 0.2

monitoring:
  metrics:
    enabled: true
    path: /metrics
  health_check:
    enabled: true
    path: /health
  prometheus:
    pushgateway: http://pushgateway:9091

features:
  fingerprinting: true
  request_validation: true
  compression: true
  docs: true
  openapi: true
  experimental: false

security:
  environment: development  # development, staging, production
  auth:
    enabled: false
    jwt_secret: your-secret-key-min-32-chars-change-in-production
    jwt_algorithm: HS256
    token_expire_minutes: 30
  rate_limiting:
    enabled: false
    per_minute: 60
    burst: 10  # requests per second
  cors:
    origins:
      - https://app.example.com
      - https://dashboard.example.com
    methods:
      - GET
      - POST
    headers:
      - Content-Type
      - Authorization
      - X-API-Key
    allow_credentials: true
  trusted_proxies:
    - 127.0.0.1
    - 10.0.0.0/8

performance:
  workers: 4
  worker_class: uvicorn.workers.UvicornWorker
  timeouts:
    request: 60
    keep_alive: 5
  concurrency:
    max_requests: 1000
    queue_size: 100
```

Load configuration from YAML:

```bash
export CONFIG_FILE=/path/to/config.yaml
python -m auditor.api.server
```

## Database Configuration

### Connection String Format

```
postgresql://[user]:[password]@[host]:[port]/[database]?[parameters]
```

**Examples**:

```bash
# Local development
DATABASE_URL=postgresql://auditor:password@localhost:5432/auditor

# With SSL
DATABASE_URL=postgresql://user:pass@host:5432/db?sslmode=require

# With connection pool settings
DATABASE_URL=postgresql://user:pass@host:5432/db?pool_size=10&max_overflow=20

# Cloud PostgreSQL (example: AWS RDS)
DATABASE_URL=postgresql://admin:pass@mydb.us-east-1.rds.amazonaws.com:5432/auditor?sslmode=require

# Cloud PostgreSQL (example: GCP Cloud SQL)
DATABASE_URL=postgresql://user:pass@/db?host=/cloudsql/project:region:instance

# Using connection parameters
DATABASE_URL=postgresql://user:pass@host:5432/db?connect_timeout=10&application_name=auditor
```

### Connection Pool Settings

Optimize for your workload:

```bash
# Low traffic (< 100 req/min)
DB_POOL_SIZE=5
DB_MAX_OVERFLOW=10

# Medium traffic (100-1000 req/min)
DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20

# High traffic (> 1000 req/min)
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=40

# Very high traffic (use PgBouncer)
# PgBouncer connection pooling recommended
```

### SSL/TLS Configuration

```bash
# Disable SSL (local development only)
DB_SSL_MODE=disable

# Prefer SSL but allow non-SSL
DB_SSL_MODE=prefer

# Require SSL (production)
DB_SSL_MODE=require
DB_SSL_ROOT_CERT=/etc/ssl/certs/ca-certificates.crt

# Verify server certificate
DB_SSL_MODE=verify-ca
DB_SSL_ROOT_CERT=/path/to/ca-cert.pem

# Verify server certificate and hostname
DB_SSL_MODE=verify-full
DB_SSL_ROOT_CERT=/path/to/ca-cert.pem
```

## API Configuration

### Server Settings

```bash
# Bind to all interfaces (default)
API_HOST=0.0.0.0

# Bind to localhost only (more secure for reverse proxy)
API_HOST=127.0.0.1

# Custom port
API_PORT=8000

# Root path (when behind reverse proxy)
API_ROOT_PATH=/api/v1
```

### CORS Configuration

```bash
# Development: Allow localhost
CORS_ORIGINS=http://localhost:3000,http://localhost:8080

# Production: Specific domains
CORS_ORIGINS=https://app.example.com,https://dashboard.example.com

# Allow all origins (NOT recommended for production)
CORS_ORIGINS=*

# Custom methods
CORS_METHODS=GET,POST,PUT,DELETE,OPTIONS

# Custom headers
CORS_HEADERS=Content-Type,Authorization,X-API-Key

# Allow credentials (cookies, auth headers)
CORS_ALLOW_CREDENTIALS=true
```

### Request Limits

```bash
# Maximum request body size (default: 10MB)
MAX_REQUEST_SIZE=10485760

# Request timeout
REQUEST_TIMEOUT=60

# Maximum concurrent requests
MAX_CONCURRENT_REQUESTS=1000
```

## NLP Model Configuration

### Model Selection

**spaCy Models**:

```bash
# Large model (best accuracy, ~500MB)
SPACY_MODEL=de_core_news_lg

# Medium model (balanced, ~100MB)
SPACY_MODEL=de_core_news_md

# Small model (fastest, ~15MB)
SPACY_MODEL=de_core_news_sm
```

**Sentence Transformer Models**:

```bash
# Best accuracy (~400MB)
EMBEDDING_MODEL=paraphrase-multilingual-mpnet-base-v2

# Faster, good accuracy (~120MB)
EMBEDDING_MODEL=paraphrase-multilingual-MiniLM-L12-v2

# Fast, decent accuracy (~80MB)
EMBEDDING_MODEL=sentence-transformers/distiluse-base-multilingual-cased-v2
```

### GPU Configuration

```bash
# Use CPU
CUDA_DEVICE=-1

# Use first GPU
CUDA_DEVICE=0

# Use specific GPU
CUDA_DEVICE=1

# Multi-GPU (not currently supported)
# CUDA_DEVICE=0,1
```

### Model Caching

```bash
# Enable caching (recommended)
ENABLE_MODEL_CACHE=true

# Custom cache directory
MODEL_CACHE_DIR=/mnt/models

# Disable caching (downloads on every startup)
ENABLE_MODEL_CACHE=false
```

### Batch Processing

```bash
# Small batches (low memory, slower)
EMBEDDING_BATCH_SIZE=8

# Medium batches (balanced)
EMBEDDING_BATCH_SIZE=32

# Large batches (high memory, faster)
EMBEDDING_BATCH_SIZE=128
```

## Processing Configuration

### Confidence Thresholds

```bash
# Default threshold for verification
DEFAULT_THRESHOLD=0.75

# Strict mode (higher threshold)
DEFAULT_THRESHOLD=0.85

# Lenient mode (lower threshold)
DEFAULT_THRESHOLD=0.65
```

### Trust Label Thresholds

The following thresholds determine trust labels:

| Confidence Range | Trust Label | Configuration |
|-----------------|-------------|---------------|
| ≥ 0.90 | Verified (High Confidence) | N/A (hardcoded) |
| 0.80 - 0.89 | Verified (Moderate Confidence) | N/A (hardcoded) |
| 0.60 - 0.79 | Review Required (Low Confidence) | N/A (hardcoded) |
| < 0.60 | Rejected (Very Low Confidence) | N/A (hardcoded) |

*Note: Custom trust label thresholds are planned for v1.1*

### Confidence Score Weights

```bash
# Semantic similarity weight (default: 0.5)
SEMANTIC_SCORE_WEIGHT=0.5

# Citation extraction weight (default: 0.3)
CITATION_SCORE_WEIGHT=0.3

# Source quality weight (default: 0.2)
SOURCE_SCORE_WEIGHT=0.2

# Sum must equal 1.0
```

### Input Limits

```bash
# Maximum sources per request
MAX_SOURCES_PER_REQUEST=100

# Maximum answer length
MAX_ANSWER_LENGTH=10000

# Maximum source text length
MAX_SOURCE_LENGTH=50000

# Minimum sentence length
MIN_SENTENCE_LENGTH=10
```

## Logging Configuration

### Log Levels

```bash
# DEBUG: Verbose debugging information
LOG_LEVEL=DEBUG

# INFO: General informational messages (default)
LOG_LEVEL=INFO

# WARNING: Warning messages
LOG_LEVEL=WARNING

# ERROR: Error messages only
LOG_LEVEL=ERROR

# CRITICAL: Critical errors only
LOG_LEVEL=CRITICAL
```

### Log Formats

**JSON Format** (recommended for production):

```bash
LOG_FORMAT=json
```

Output:
```json
{
  "timestamp": "2025-10-30T10:15:30.123Z",
  "level": "INFO",
  "logger": "auditor.api.server",
  "message": "Verification completed",
  "extra": {
    "answer_length": 150,
    "num_sources": 3,
    "confidence": 0.92
  }
}
```

**Text Format** (human-readable):

```bash
LOG_FORMAT=text
```

Output:
```
2025-10-30 10:15:30,123 - INFO - auditor.api.server - Verification completed
```

### Log Output

```bash
# Log to stdout (default, good for Docker)
LOG_OUTPUT=stdout

# Log to file
LOG_OUTPUT=file
LOG_FILE=/var/log/auditor/app.log

# Log to both stdout and file
LOG_OUTPUT=both
LOG_FILE=/var/log/auditor/app.log
```

### Specialized Logging

```bash
# Enable access logs (HTTP requests)
ENABLE_ACCESS_LOGS=true

# Enable SQL query logs (debugging only)
ENABLE_SQL_LOGS=false  # WARNING: Very verbose
```

## Monitoring Configuration

### Prometheus Metrics

```bash
# Enable metrics endpoint
ENABLE_METRICS=true

# Metrics endpoint path
METRICS_PATH=/metrics

# Prometheus pushgateway (for batch jobs)
PROMETHEUS_PUSHGATEWAY=http://pushgateway:9091
```

### Health Checks

```bash
# Enable health check endpoint
ENABLE_HEALTH_CHECK=true

# Health check path
HEALTH_CHECK_PATH=/health
```

Health check response:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "database": "connected",
  "models": "loaded"
}
```

## Security Configuration

### Overview

JuraGPT Auditor implements enterprise-grade security with:

- **Authentication**: JWT tokens and API keys
- **Rate Limiting**: Sliding window algorithm with burst protection
- **Security Headers**: OWASP Top 10 compliance
- **CORS**: Environment-based configuration

All security features are **optional** and **disabled by default** for backward compatibility.

### Authentication

**Enable Authentication**:

```bash
# Enable authentication (default: false)
ENABLE_AUTH=true

# JWT secret key (REQUIRED if ENABLE_AUTH=true, min 32 characters)
JWT_SECRET_KEY=your-very-secret-key-min-32-characters-change-in-production

# JWT signing algorithm (default: HS256)
JWT_ALGORITHM=HS256

# JWT token expiration in minutes (default: 30)
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
```

**⚠️ Security Requirements**:

- `JWT_SECRET_KEY` must be at least 32 characters
- Use a cryptographically secure random string in production
- Never commit secrets to version control
- Rotate JWT secrets periodically (every 90 days recommended)

**Generate Strong Secret**:

```bash
# Generate 32-character secret
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# Or use openssl
openssl rand -base64 32
```

**Demo Users** (change in production!):

The application includes two demo users for testing:

| Username | Password | Scopes | Access Level |
|----------|----------|--------|--------------|
| `admin` | `admin123` | `admin`, `verify` | Full access including API key management |
| `demo` | `demo123` | `verify` | Verification access only |

**Production**: Replace demo users with real user database or external auth provider.

### API Keys

API keys provide long-lived authentication for programmatic access:

**Configuration**:

```bash
# API key header name (default: X-API-Key)
API_KEY_HEADER=X-API-Key
```

**Features**:

- Cryptographically secure generation (64+ characters)
- Bcrypt hashing for storage
- Per-key rate limits
- Per-key scopes (permissions)
- Expiration support (days)
- Revocation support

**Create API Key** (via API after authenticating):

```bash
curl -X POST http://localhost:8888/auth/api-keys \
  -H "Authorization: Bearer <admin-jwt-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "production-app",
    "scopes": ["verify"],
    "rate_limit": 500,
    "expires_in_days": 90
  }'
```

**Response**:

```json
{
  "api_key": "ak_abc123def456...",
  "key_id": "production-app-a1b2c3d4",
  "user_id": "admin",
  "scopes": ["verify"],
  "rate_limit": 500,
  "created_at": "2025-10-30T10:00:00Z",
  "expires_at": "2026-01-28T10:00:00Z"
}
```

**⚠️ Important**: The `api_key` is shown only once. Store it securely.

### Rate Limiting

**Enable Rate Limiting**:

```bash
# Enable rate limiting (default: false)
ENABLE_RATE_LIMITING=true

# Requests per minute per client (default: 60)
RATE_LIMIT_PER_MINUTE=60

# Burst protection: requests per second (default: 10)
RATE_LIMIT_BURST=10
```

**Algorithm**: Sliding window with burst protection

- **Per-minute limit**: Tracks requests over rolling 60-second window
- **Burst limit**: Prevents rapid-fire requests (e.g., 100 requests in 1 second)
- **Client identification**: IP address or API key
- **Response headers**: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`

**Custom Limits per API Key**:

API keys can override the default rate limit:

```bash
# Default rate limit
RATE_LIMIT_PER_MINUTE=60

# API key with custom 500 req/min limit
# Set via POST /auth/api-keys with "rate_limit": 500
```

**Rate Limit Response**:

When limit exceeded, API returns `429 Too Many Requests`:

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

### Security Headers

Security headers are **always enabled** and comply with OWASP Top 10:

**Applied Headers**:

| Header | Value | Purpose |
|--------|-------|---------|
| `X-Frame-Options` | `DENY` | Prevent clickjacking |
| `X-Content-Type-Options` | `nosniff` | Prevent MIME sniffing |
| `X-XSS-Protection` | `1; mode=block` | Enable XSS protection |
| `Referrer-Policy` | `strict-origin-when-cross-origin` | Control referrer |
| `Permissions-Policy` | `camera=(), microphone=(), ...` | Restrict features |
| `Content-Security-Policy` | `default-src 'self'; ...` | Prevent XSS/injection |
| `Strict-Transport-Security` | `max-age=31536000` (prod only) | Enforce HTTPS |

**HSTS (HTTP Strict Transport Security)**:

HSTS is enabled automatically in production:

```bash
# Set environment to enable HSTS
ENVIRONMENT=production
```

When `ENVIRONMENT=production`:

```
Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
```

When `ENVIRONMENT=development`:

- HSTS is disabled to allow HTTP testing

**Content Security Policy**:

```
Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'
```

**Permissions Policy**:

```
Permissions-Policy: camera=(), microphone=(), geolocation=(), interest-cohort=(), payment=(), usb=()
```

### CORS Configuration

CORS is configured based on environment:

```bash
# CORS allowed origins (comma-separated, default: * in development)
CORS_ORIGINS=https://app.example.com,https://dashboard.example.com

# CORS allowed methods (comma-separated, default: GET,POST)
CORS_METHODS=GET,POST,PUT,DELETE,OPTIONS

# CORS allowed headers (comma-separated)
CORS_HEADERS=Content-Type,Authorization,X-API-Key

# CORS allow credentials (default: true)
CORS_ALLOW_CREDENTIALS=true
```

**Development** (default):

```bash
CORS_ORIGINS=*  # Allow all origins
ENVIRONMENT=development
```

**Production**:

```bash
CORS_ORIGINS=https://app.example.com,https://dashboard.example.com
ENVIRONMENT=production
```

**Exposed Headers**:

Rate limit headers are always exposed to clients:

- `X-RateLimit-Limit`
- `X-RateLimit-Remaining`
- `X-RateLimit-Reset`

### Environment Configuration

```bash
# Environment: development, staging, production (default: development)
ENVIRONMENT=production
```

**Environment Effects**:

| Feature | Development | Production |
|---------|-------------|------------|
| CORS | `*` (all origins) | Specific origins only |
| HSTS | Disabled | Enabled |
| Debug logs | Enabled | Disabled |
| Error details | Full stack traces | Generic messages |
| API docs | Enabled | Optional |

### Security Best Practices

**Production Checklist**:

1. ✅ Enable authentication: `ENABLE_AUTH=true`
2. ✅ Enable rate limiting: `ENABLE_RATE_LIMITING=true`
3. ✅ Set strong JWT secret: 32+ characters, cryptographically random
4. ✅ Configure CORS origins: Specific domains only
5. ✅ Set environment: `ENVIRONMENT=production`
6. ✅ Use HTTPS: Always in production
7. ✅ Rotate secrets: JWT secret every 90 days
8. ✅ Monitor access: Check logs for unauthorized attempts
9. ✅ Update dependencies: Regular security updates
10. ✅ Remove demo users: Replace with real authentication

**Production Security Configuration Example**:

```bash
# Security settings for production
ENVIRONMENT=production

# Authentication
ENABLE_AUTH=true
JWT_SECRET_KEY=<64-char-random-string>
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30

# Rate limiting
ENABLE_RATE_LIMITING=true
RATE_LIMIT_PER_MINUTE=100
RATE_LIMIT_BURST=20

# CORS
CORS_ORIGINS=https://app.example.com,https://api.example.com
CORS_METHODS=GET,POST
CORS_HEADERS=Content-Type,Authorization,X-API-Key
CORS_ALLOW_CREDENTIALS=true
```

### Trusted Proxies

When behind a reverse proxy or load balancer, configure trusted IPs for correct client IP detection:

```bash
# Single proxy
TRUSTED_PROXIES=127.0.0.1

# Multiple proxies (comma-separated)
TRUSTED_PROXIES=127.0.0.1,10.0.0.1

# CIDR notation
TRUSTED_PROXIES=10.0.0.0/8,172.16.0.0/12,192.168.0.0/16

# Cloud load balancers
TRUSTED_PROXIES=10.0.0.0/8,172.16.0.0/12
```

**Why This Matters**:

- Rate limiting uses client IP address
- Without trusted proxies, all requests appear to come from the proxy
- Configure to extract real client IP from `X-Forwarded-For` header

## Performance Tuning

### Worker Configuration

```bash
# Auto-detect CPU cores
WORKER_COUNT=0

# Specific number of workers
WORKER_COUNT=4

# Formula: (2 x $num_cores) + 1
WORKER_COUNT=9  # For 4-core server
```

### Concurrency Limits

```bash
# Maximum concurrent requests
MAX_CONCURRENT_REQUESTS=1000

# Request queue size
REQUEST_QUEUE_SIZE=100

# Enable queuing
ENABLE_REQUEST_QUEUE=true
```

### Timeouts

```bash
# Request processing timeout
REQUEST_TIMEOUT=60

# Keep-alive timeout
KEEP_ALIVE=5

# Database connection timeout
DB_CONNECT_TIMEOUT=10

# Database pool timeout
DB_POOL_TIMEOUT=30
```

### Memory Optimization

```bash
# Reduce embedding batch size
EMBEDDING_BATCH_SIZE=16

# Reduce database pool size
DB_POOL_SIZE=5

# Disable model caching (not recommended)
ENABLE_MODEL_CACHE=false
```

## Feature Flags

```bash
# Core features
ENABLE_FINGERPRINTING=true        # Source fingerprinting
ENABLE_REQUEST_VALIDATION=true    # Input validation
ENABLE_COMPRESSION=true           # Response compression

# API documentation
ENABLE_DOCS=true                  # Swagger UI at /docs
ENABLE_OPENAPI=true               # OpenAPI schema at /openapi.json

# Experimental features (v1.1+)
ENABLE_EXPERIMENTAL=false         # Unstable features
ENABLE_BATCH_API=false            # Batch verification endpoint
ENABLE_ASYNC_PROCESSING=false     # Async job processing
```

## Docker Configuration

### Environment File (.env)

```bash
# .env file for docker-compose
DATABASE_URL=postgresql://auditor:auditor_password@postgres:5432/auditor
API_PORT=8000
LOG_LEVEL=INFO
ENABLE_METRICS=true
```

### Docker Compose Override

Create `docker-compose.override.yml`:

```yaml
version: '3.8'

services:
  auditor-api:
    environment:
      - LOG_LEVEL=DEBUG
      - ENABLE_SQL_LOGS=true
    ports:
      - "8888:8000"  # Custom port mapping
```

## Kubernetes Configuration

### ConfigMap

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: auditor-config
  namespace: auditor
data:
  LOG_LEVEL: "INFO"
  LOG_FORMAT: "json"
  ENABLE_METRICS: "true"
  DEFAULT_THRESHOLD: "0.75"
  SPACY_MODEL: "de_core_news_lg"
```

### Secret

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: auditor-secrets
  namespace: auditor
type: Opaque
stringData:
  DATABASE_URL: "postgresql://user:pass@postgres:5432/auditor"
  JWT_SECRET_KEY: "your-secret-key-min-32-characters"
```

### Deployment with ConfigMap

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: auditor-api
spec:
  template:
    spec:
      containers:
      - name: auditor-api
        image: juragpt-auditor:latest
        envFrom:
        - configMapRef:
            name: auditor-config
        - secretRef:
            name: auditor-secrets
```

## Configuration Validation

The application validates configuration on startup using Pydantic:

```python
from auditor.config.settings import Settings

try:
    settings = Settings()
    print("✅ Configuration valid")
except ValidationError as e:
    print("❌ Configuration errors:")
    print(e)
```

**Common validation errors**:

```
DATABASE_URL
  field required (type=value_error.missing)

DEFAULT_THRESHOLD
  ensure this value is less than or equal to 1.0 (type=value_error.number.not_le; limit_value=1.0)

LOG_LEVEL
  unexpected value; permitted: 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL' (type=value_error.const)
```

## Examples

### Development Environment

```bash
# .env.development
DATABASE_URL=postgresql://auditor:auditor@localhost:5432/auditor_dev
API_PORT=8000
LOG_LEVEL=DEBUG
ENABLE_SQL_LOGS=true
ENABLE_ACCESS_LOGS=true
ENABLE_DOCS=true
ENABLE_METRICS=true
CUDA_DEVICE=-1
WORKER_COUNT=1
```

### Production Environment

```bash
# .env.production
# Database
DATABASE_URL=postgresql://user:pass@db.internal:5432/auditor?sslmode=require

# API
API_HOST=127.0.0.1
API_PORT=8000
API_ROOT_PATH=/api/v1

# Logging
LOG_LEVEL=INFO
LOG_FORMAT=json
LOG_OUTPUT=stdout
ENABLE_SQL_LOGS=false
ENABLE_ACCESS_LOGS=true

# Features
ENABLE_DOCS=false
ENABLE_METRICS=true

# Security
ENVIRONMENT=production
ENABLE_AUTH=true
JWT_SECRET_KEY=<64-char-cryptographically-secure-random-string>
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30

ENABLE_RATE_LIMITING=true
RATE_LIMIT_PER_MINUTE=100
RATE_LIMIT_BURST=20

CORS_ORIGINS=https://app.example.com,https://dashboard.example.com
CORS_METHODS=GET,POST
CORS_HEADERS=Content-Type,Authorization,X-API-Key
CORS_ALLOW_CREDENTIALS=true

TRUSTED_PROXIES=10.0.0.0/8,172.16.0.0/12

# Performance
WORKER_COUNT=8
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=40
CUDA_DEVICE=0
```

### High-Performance Configuration

```bash
# .env.performance
DATABASE_URL=postgresql://user:pass@db:5432/auditor
WORKER_COUNT=16
MAX_CONCURRENT_REQUESTS=2000
REQUEST_QUEUE_SIZE=500
DB_POOL_SIZE=30
DB_MAX_OVERFLOW=60
EMBEDDING_BATCH_SIZE=64
CUDA_DEVICE=0
ENABLE_MODEL_CACHE=true
MODEL_CACHE_DIR=/mnt/fast-storage/models
REQUEST_TIMEOUT=30
KEEP_ALIVE=2
```

### Low-Resource Configuration

```bash
# .env.low-resource
DATABASE_URL=postgresql://user:pass@db:5432/auditor
WORKER_COUNT=2
MAX_CONCURRENT_REQUESTS=100
DB_POOL_SIZE=3
DB_MAX_OVERFLOW=5
EMBEDDING_BATCH_SIZE=8
CUDA_DEVICE=-1
SPACY_MODEL=de_core_news_sm
EMBEDDING_MODEL=paraphrase-multilingual-MiniLM-L12-v2
ENABLE_MODEL_CACHE=true
```

---

For more information, see:
- [API Documentation](API.md)
- [Architecture Documentation](ARCHITECTURE.md)
- [Deployment Guide](DEPLOYMENT.md)
- [Contributing Guide](CONTRIBUTING.md)
