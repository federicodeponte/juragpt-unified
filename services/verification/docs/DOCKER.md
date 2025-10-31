# Docker Deployment Guide

Complete guide for deploying JuraGPT Auditor using Docker and Docker Compose.

---

## Table of Contents

- [Quick Start](#quick-start)
- [Architecture](#architecture)
- [Building](#building)
- [Configuration](#configuration)
- [Running](#running)
- [Volumes & Data Persistence](#volumes--data-persistence)
- [Networking](#networking)
- [Model Caching](#model-caching)
- [Monitoring](#monitoring)
- [Production Deployment](#production-deployment)
- [Troubleshooting](#troubleshooting)

---

## Quick Start

### Prerequisites

- Docker Engine 20.10+ ([Install Docker](https://docs.docker.com/engine/install/))
- Docker Compose 2.0+ ([Install Compose](https://docs.docker.com/compose/install/))
- 4GB+ RAM (for model loading)
- 10GB+ disk space (for models and data)

### Start Full Stack (Recommended)

```bash
# 1. Clone repository
git clone https://github.com/your-org/juragpt-auditor.git
cd juragpt-auditor

# 2. Create environment file
cp .env.example .env
# Edit .env with your passwords (optional for local testing)

# 3. Start all services
docker-compose up -d

# 4. Check service health
docker-compose ps

# 5. Access services
# - API: http://localhost:8000
# - API Docs: http://localhost:8000/docs
# - Prometheus: http://localhost:9090
# - Grafana: http://localhost:3000 (admin/admin)
```

### Start API Only

```bash
# Build and run just the API service
docker-compose up -d auditor-api postgres
```

### Stop All Services

```bash
docker-compose down
```

### Stop and Remove Data

```bash
docker-compose down -v  # WARNING: Deletes all data volumes
```

---

## Architecture

### Multi-Stage Dockerfile

The Dockerfile uses a two-stage build process for optimization:

```
┌─────────────────────────────────────────┐
│ Stage 1: Builder                        │
│ - Install build dependencies           │
│ - Download spaCy model (de_core_news_md)│
│ - Pre-download embeddings (e5-large)    │
│ - Size: ~5GB (discarded)                │
└─────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────┐
│ Stage 2: Runtime                        │
│ - Minimal Python 3.11 base              │
│ - Copy models from builder              │
│ - Non-root user (security)              │
│ - Health checks enabled                 │
│ - Size: ~2.5GB (production)             │
└─────────────────────────────────────────┘
```

### Docker Compose Services

```
┌──────────────┐      ┌──────────────┐
│  auditor-api │─────▶│   postgres   │
│  Port: 8000  │      │  Port: 5432  │
└──────┬───────┘      └──────────────┘
       │
       │ /metrics
       ▼
┌──────────────┐      ┌──────────────┐
│  prometheus  │─────▶│   grafana    │
│  Port: 9090  │      │  Port: 3000  │
└──────────────┘      └──────────────┘
```

---

## Building

### Build from Dockerfile

```bash
# Build the image
docker build -t juragpt-auditor:latest .

# Build with custom tag
docker build -t juragpt-auditor:1.0.0 .

# Build with no cache (force fresh build)
docker build --no-cache -t juragpt-auditor:latest .
```

### Build Time Optimization

**First build:** ~10-15 minutes (downloading models ~2GB)
**Subsequent builds:** ~2-5 minutes (Docker layer caching)

**Tips for faster builds:**
- Models are cached in Docker layers
- Use `--cache-from` for CI/CD pipelines
- Keep `src/` changes small to maximize cache hits

### Multi-Platform Builds

```bash
# Build for multiple architectures
docker buildx build --platform linux/amd64,linux/arm64 -t juragpt-auditor:latest .
```

---

## Configuration

### Environment Variables

Edit `.env` file or set in `docker-compose.yml`:

#### Database

```bash
# PostgreSQL (production)
DATABASE_URL=postgresql://auditor:password@postgres:5432/auditor
POSTGRES_PASSWORD=your-secure-password

# SQLite (local development)
DATABASE_URL=sqlite:////app/data/auditor.db
```

#### Models

```bash
EMBEDDING_MODEL=intfloat/multilingual-e5-large
SPACY_MODEL=de_core_news_md
```

#### Performance

```bash
CACHE_ENABLED=true
CACHE_SIZE=1000
BATCH_SIZE=32
```

#### Security

```bash
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR
```

#### Monitoring

```bash
GRAFANA_PASSWORD=your-admin-password
```

### Override Configuration

```bash
# Use custom config.yaml
docker-compose up -d \
  -v $(pwd)/custom-config.yaml:/app/config.yaml:ro
```

---

## Running

### Development Mode

```bash
# Run with live code reload
docker-compose -f docker-compose.dev.yml up

# View logs
docker-compose logs -f auditor-api

# Execute commands in container
docker-compose exec auditor-api bash
```

### Production Mode

```bash
# Start in detached mode
docker-compose up -d

# Check health
curl http://localhost:8000/health

# View resource usage
docker stats auditor-api
```

### Restart Services

```bash
# Restart single service
docker-compose restart auditor-api

# Restart all services
docker-compose restart
```

### Scale Services

```bash
# Run multiple API instances (requires load balancer)
docker-compose up -d --scale auditor-api=3
```

---

## Volumes & Data Persistence

### Managed Volumes

Docker Compose automatically creates persistent volumes:

```yaml
volumes:
  postgres-data:     # Database persistence
  model-cache:       # ML models (optional)
  prometheus-data:   # Metrics history (15 days)
  grafana-data:      # Dashboard configurations
```

### Inspect Volumes

```bash
# List all volumes
docker volume ls | grep auditor

# Inspect volume details
docker volume inspect auditor_postgres-data

# View volume contents
docker run --rm -v auditor_postgres-data:/data alpine ls -la /data
```

### Backup Volumes

```bash
# Backup PostgreSQL
docker-compose exec postgres pg_dump -U auditor auditor > backup.sql

# Backup volume to tar
docker run --rm -v auditor_postgres-data:/data -v $(pwd):/backup \
  alpine tar czf /backup/postgres-backup.tar.gz /data
```

### Restore Volumes

```bash
# Restore PostgreSQL
cat backup.sql | docker-compose exec -T postgres psql -U auditor auditor

# Restore volume from tar
docker run --rm -v auditor_postgres-data:/data -v $(pwd):/backup \
  alpine sh -c "cd /data && tar xzf /backup/postgres-backup.tar.gz --strip 1"
```

---

## Networking

### Internal Network

All services communicate via `auditor-network` bridge network.

**Service DNS names:**
- `auditor-api` - API service
- `postgres` - Database
- `prometheus` - Metrics
- `grafana` - Dashboards

### Port Mapping

| Service | Internal Port | External Port |
|---------|---------------|---------------|
| API | 8000 | 8000 |
| PostgreSQL | 5432 | 5432 |
| Prometheus | 9090 | 9090 |
| Grafana | 3000 | 3000 |

### Expose Ports

```yaml
# Expose only API (hide other services)
services:
  auditor-api:
    ports:
      - "8000:8000"
  postgres:
    # No external port mapping
  prometheus:
    # No external port mapping
  grafana:
    ports:
      - "3000:3000"  # Only Grafana
```

---

## Model Caching

### How Models are Cached

1. **Build time:** Models downloaded in builder stage
2. **Image layer:** Models stored in Docker layer
3. **Runtime:** Models copied to `/home/auditor/.cache`

### Model Cache Directories

```
/home/auditor/.cache/
├── torch/                    # Sentence transformers (~2GB)
│   └── sentence_transformers/
└── /home/auditor/.local/share/spacy/  # spaCy model (~50MB)
    └── de_core_news_md/
```

### Update Models

```bash
# Rebuild image to update models
docker-compose build --no-cache auditor-api

# Or mount custom models
docker-compose up -d \
  -v /path/to/models:/home/auditor/.cache:ro
```

### Verify Models Loaded

```bash
docker-compose exec auditor-api python -c "
from sentence_transformers import SentenceTransformer
import spacy

# Check embedding model
model = SentenceTransformer('intfloat/multilingual-e5-large')
print('✓ Embedding model loaded')

# Check spaCy model
nlp = spacy.load('de_core_news_md')
print('✓ spaCy model loaded')
"
```

---

## Monitoring

### Access Monitoring Stack

**Prometheus:** http://localhost:9090
- Metrics explorer
- Query language (PromQL)
- Alert rules

**Grafana:** http://localhost:3000
- Default login: `admin` / `admin` (change in .env)
- Pre-configured dashboards
- Real-time visualization

### Available Metrics

```promql
# Request rate
rate(auditor_verify_requests_total[5m])

# Latency percentiles
histogram_quantile(0.95, auditor_verify_latency_seconds_bucket)

# Confidence score distribution
auditor_confidence_score_bucket
```

### Health Checks

```bash
# Check all services
docker-compose ps

# Check API health
curl http://localhost:8000/health

# Check Prometheus targets
curl http://localhost:9090/api/v1/targets

# Check Grafana health
curl http://localhost:3000/api/health
```

---

## Production Deployment

### Security Checklist

- [ ] Change default passwords in `.env`
- [ ] Use secrets management (Docker secrets, Vault)
- [ ] Enable HTTPS (reverse proxy)
- [ ] Restrict port access (firewall)
- [ ] Set resource limits (memory, CPU)
- [ ] Enable authentication (API keys)
- [ ] Review security scans (`docker scan`)

### Resource Limits

```yaml
# docker-compose.override.yml
services:
  auditor-api:
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 4G
        reservations:
          cpus: '1.0'
          memory: 2G
```

### High Availability

```yaml
# Run multiple API replicas
services:
  auditor-api:
    deploy:
      replicas: 3
      restart_policy:
        condition: on-failure
        max_attempts: 3
```

### Reverse Proxy (nginx)

```nginx
# /etc/nginx/sites-available/auditor
server {
    listen 443 ssl http2;
    server_name auditor.example.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

## Troubleshooting

### Container Won't Start

```bash
# Check logs
docker-compose logs auditor-api

# Check container status
docker-compose ps

# Inspect container
docker inspect auditor-api
```

### Out of Memory

```bash
# Check memory usage
docker stats

# Increase Docker memory limit (Docker Desktop)
# Settings → Resources → Memory → 6GB

# Or reduce model size
EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
```

### Model Download Fails

```bash
# Rebuild with verbose output
docker-compose build --progress=plain auditor-api

# Check network
docker run --rm alpine ping -c 3 huggingface.co

# Use proxy (if behind firewall)
docker build --build-arg HTTP_PROXY=http://proxy:8080 -t auditor .
```

### Database Connection Issues

```bash
# Check PostgreSQL is running
docker-compose logs postgres

# Test connection
docker-compose exec postgres psql -U auditor -d auditor -c "SELECT 1;"

# Reset database
docker-compose down -v postgres
docker-compose up -d postgres
```

### Permission Denied Errors

```bash
# Fix volume permissions
docker-compose exec auditor-api chown -R auditor:auditor /home/auditor/.cache

# Or run as root (NOT recommended for production)
docker-compose run --user root auditor-api bash
```

### Slow Performance

```bash
# Check resource usage
docker stats

# Reduce cache size
CACHE_SIZE=500

# Disable cache temporarily
CACHE_ENABLED=false

# Use smaller embedding model
EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
```

---

## Advanced Topics

### Custom Entrypoint

```dockerfile
# Custom startup script
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh
ENTRYPOINT ["docker-entrypoint.sh"]
```

### Multi-Stage Testing

```yaml
# docker-compose.test.yml
services:
  test:
    build:
      context: .
      target: builder  # Stop at builder stage
    command: pytest tests/ -v
```

### CI/CD Integration

```yaml
# .github/workflows/docker.yml
- name: Build and test
  run: |
    docker build -t auditor:test .
    docker run auditor:test pytest
```

---

## Additional Resources

- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Reference](https://docs.docker.com/compose/compose-file/)
- [Best Practices](https://docs.docker.com/develop/dev-best-practices/)
- [Security Guide](https://docs.docker.com/engine/security/)

---

**Questions or issues?** [Open an issue](https://github.com/your-org/juragpt-auditor/issues)

**Last Updated:** 2025-10-29
