# JuraGPT Unified - Deployment Guide

Production deployment guide for JuraGPT Unified microservices.

## Prerequisites

- Docker 20.10+ & Docker Compose 2.0+
- Python 3.11+
- 16GB RAM minimum (32GB recommended)
- PostgreSQL 15+
- Qdrant Cloud account
- Modal account (for GPU embeddings, optional)

## Quick Start

```bash
# 1. Clone repository
git clone https://github.com/federicodeponte/juragpt-unified.git
cd juragpt-unified

# 2. Configure environment
cp .env.example .env
# Edit .env with your credentials

# 3. Deploy with Docker Compose
docker-compose up -d

# 4. Verify all services healthy
curl http://localhost:8888/health
```

## Environment Configuration

### Required Variables

```bash
# Qdrant Vector Database
QDRANT_URL=https://your-cluster.qdrant.io
QDRANT_API_KEY=your-qdrant-api-key

# PostgreSQL Database
DATABASE_URL=postgresql://user:password@postgres:5432/juragpt
DATABASE_PASSWORD=secure-password

# JWT Authentication
JWT_SECRET_KEY=your-secret-key-min-32-chars

# Feature Flags
ENABLE_AUTH=true
ENABLE_METRICS=true
```

### Optional Variables

```bash
# Service URLs (Docker Compose sets these automatically)
EMBEDDER_URL=http://embedder:8003
RETRIEVAL_URL=http://retrieval:8001
VERIFICATION_URL=http://verification:8002

# Model Configuration
EMBEDDING_MODEL=intfloat/multilingual-e5-large

# Monitoring
GRAFANA_PASSWORD=admin
```

## Docker Compose Deployment

### Production Configuration

```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f orchestrator

# Stop all services
docker-compose down

# Stop and remove volumes (DELETES DATA!)
docker-compose down -v
```

### Service Health Checks

```bash
# Overall system health
curl http://localhost:8888/health

# Individual service health
curl http://localhost:8001/health  # Retrieval
curl http://localhost:8002/health  # Verification
curl http://localhost:8003/health  # Embedder

# Grafana dashboards
open http://localhost:3000  # admin/admin
```

## Manual Deployment (Without Docker)

### 1. Install Dependencies

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Install base requirements
pip install -r requirements.txt

# Install service-specific requirements
pip install -r services/embedder/requirements.txt
pip install -r services/retrieval/requirements.txt
pip install -r services/verification/requirements.txt
pip install -r services/orchestrator/requirements.txt
```

### 2. Setup Databases

```bash
# PostgreSQL (for verification history)
createdb juragpt
psql juragpt < services/verification/schema.sql

# Qdrant (use Qdrant Cloud or local Docker)
docker run -p 6333:6333 qdrant/qdrant
```

### 3. Start Services (in order)

```bash
# Terminal 1: Embedder (must start first)
cd services/embedder
uvicorn main:app --host 0.0.0.0 --port 8003

# Terminal 2: Retrieval
cd services/retrieval
uvicorn main:app --host 0.0.0.0 --port 8001

# Terminal 3: Verification
cd services/verification
uvicorn main:app --host 0.0.0.0 --port 8002

# Terminal 4: Orchestrator
cd services/orchestrator
uvicorn main:app --host 0.0.0.0 --port 8888
```

## Kubernetes Deployment

```yaml
# k8s/deployment.yaml (example)
apiVersion: apps/v1
kind: Deployment
metadata:
  name: embedder
spec:
  replicas: 2
  template:
    spec:
      containers:
      - name: embedder
        image: juragpt-embedder:latest
        resources:
          requests:
            memory: "4Gi"
            cpu: "1000m"
          limits:
            memory: "8Gi"
            cpu: "2000m"
```

Deploy:
```bash
kubectl apply -f k8s/
kubectl get pods -n juragpt
```

## Production Checklist

### Security

- [ ] Change default passwords (JWT_SECRET_KEY, DATABASE_PASSWORD, GRAFANA_PASSWORD)
- [ ] Enable HTTPS/TLS (use nginx reverse proxy or Traefik)
- [ ] Configure CORS properly (restrict origins)
- [ ] Enable rate limiting
- [ ] Set up firewall rules (only expose orchestrator:8888)
- [ ] Use secrets management (AWS Secrets Manager, HashiCorp Vault)
- [ ] Enable PostgreSQL SSL
- [ ] Review Qdrant Cloud security settings

### Data

- [ ] Backup PostgreSQL database regularly
- [ ] Configure Qdrant Cloud backups
- [ ] Set up log rotation
- [ ] Monitor disk usage

### Monitoring

- [ ] Configure Prometheus scraping
- [ ] Set up Grafana dashboards
- [ ] Enable error alerting (PagerDuty, Slack)
- [ ] Configure health check monitoring (UptimeRobot)
- [ ] Set up application performance monitoring (APM)

### Scaling

- [ ] Load test with realistic traffic
- [ ] Configure horizontal pod autoscaling (Kubernetes)
- [ ] Set up CDN for static assets
- [ ] Optimize database queries
- [ ] Enable connection pooling (PostgreSQL)

## Resource Requirements

### Minimum (Development)

- CPU: 4 cores
- RAM: 16GB
- Disk: 50GB

### Recommended (Production)

- CPU: 8 cores
- RAM: 32GB
- Disk: 200GB SSD

### Per-Service Requirements

| Service | CPU | RAM | Disk |
|---------|-----|-----|------|
| Embedder | 2 cores | 8GB | 5GB |
| Retrieval | 1 core | 2GB | 10GB |
| Verification | 1 core | 2GB | 20GB |
| Orchestrator | 1 core | 1GB | 1GB |
| PostgreSQL | 2 cores | 4GB | 50GB |
| Prometheus | 1 core | 2GB | 50GB |
| Grafana | 1 core | 1GB | 5GB |

## Troubleshooting

### Services Won't Start

```bash
# Check Docker logs
docker-compose logs embedder

# Check if ports are in use
lsof -i :8003  # Embedder
lsof -i :8001  # Retrieval
lsof -i :8002  # Verification
lsof -i :8888  # Orchestrator

# Verify environment variables
docker-compose config
```

### Embedder Out of Memory

```bash
# Increase Docker memory limit
# Edit docker-compose.yml:
services:
  embedder:
    deploy:
      resources:
        limits:
          memory: 16G  # Increase from 8G
```

### Qdrant Connection Failed

```bash
# Test connection
curl -X GET "$QDRANT_URL/collections" \
  -H "api-key: $QDRANT_API_KEY"

# Check network connectivity
ping your-cluster.qdrant.io
```

### PostgreSQL Connection Issues

```bash
# Test connection
psql "$DATABASE_URL"

# Check if PostgreSQL is running
docker-compose ps postgres

# View PostgreSQL logs
docker-compose logs postgres
```

## Backup & Recovery

### PostgreSQL Backup

```bash
# Manual backup
docker-compose exec postgres pg_dump -U juragpt juragpt > backup.sql

# Restore from backup
cat backup.sql | docker-compose exec -T postgres psql -U juragpt juragpt
```

### Qdrant Backup

Use Qdrant Cloud's built-in backup feature or:

```python
# Export collection to disk
from qdrant_client import QdrantClient

client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)
client.snapshot.create(collection_name="legal_documents")
```

## Performance Tuning

### Optimize Embedder

```python
# Use GPU acceleration (Modal)
# Edit services/embedder/main.py to use Modal GPU endpoint
# See Modal documentation: https://modal.com/docs

# Batch requests
# Group multiple texts into single /embed request
```

### Optimize Qdrant

```bash
# Increase memory limit
# Qdrant Cloud: upgrade plan

# Enable HNSW index optimization
# See Qdrant docs: https://qdrant.tech/documentation/guides/optimization/
```

### Optimize PostgreSQL

```sql
-- Add indexes for common queries
CREATE INDEX idx_verification_timestamp ON verification_history(created_at);
CREATE INDEX idx_verification_confidence ON verification_history(confidence);

-- Enable query plan caching
ALTER SYSTEM SET shared_preload_libraries = 'pg_stat_statements';
```

## Monitoring Dashboards

### Grafana Dashboards

Access: `http://localhost:3000` (admin/admin)

**Dashboards Included**:
1. System Overview - Request rates, latency, errors
2. Retrieval Performance - Vector search metrics, hit rate
3. Verification Metrics - Confidence distribution, low-confidence alerts
4. Resource Usage - CPU, memory, disk per service

### Prometheus Queries

```promql
# Request rate
rate(http_requests_total[5m])

# P95 latency
histogram_quantile(0.95, http_request_duration_seconds_bucket)

# Error rate
rate(http_requests_total{status=~"5.."}[5m])

# Low confidence verifications
verification_confidence{confidence<0.7}
```

## Upgrading

```bash
# 1. Pull latest code
git pull origin main

# 2. Stop services
docker-compose down

# 3. Rebuild images
docker-compose build

# 4. Start services
docker-compose up -d

# 5. Run database migrations (if any)
docker-compose exec verification alembic upgrade head
```

## Cost Estimation

### Monthly Costs (Production)

- **Qdrant Cloud**: $50-200/month (depends on vector count)
- **PostgreSQL** (managed): $30-100/month
- **Compute** (AWS EC2 t3.xlarge): $120/month
- **Monitoring**: $0 (self-hosted Prometheus/Grafana)
- **Modal GPU** (optional): $50-200/month (usage-based)

**Total**: $250-620/month

## Support & Maintenance

### Health Monitoring

Set up automated health checks:

```bash
# Create systemd service for health checks
sudo cat > /etc/systemd/system/juragpt-health.service << 'EOF'
[Unit]
Description=JuraGPT Health Check
After=network.target

[Service]
Type=oneshot
ExecStart=/usr/bin/curl -f http://localhost:8888/health || /usr/bin/systemctl restart docker-compose@juragpt

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl enable juragpt-health.timer
```

### Log Aggregation

Use centralized logging:

```yaml
# docker-compose.yml
services:
  orchestrator:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

Or integrate with ELK Stack, Loki, or Datadog.

## References

- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Kubernetes Documentation](https://kubernetes.io/docs/)
- [Qdrant Cloud](https://qdrant.tech/documentation/cloud/)
- [FastAPI Deployment](https://fastapi.tiangolo.com/deployment/)
- [PostgreSQL Tuning](https://wiki.postgresql.org/wiki/Tuning_Your_PostgreSQL_Server)
