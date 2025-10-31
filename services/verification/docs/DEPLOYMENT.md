# Deployment Guide

Comprehensive guide for deploying the JuraGPT Auditor verification service to production.

## Table of Contents

- [Overview](#overview)
- [Deployment Options](#deployment-options)
- [Docker Compose](#docker-compose)
- [Kubernetes](#kubernetes)
- [Cloud Providers](#cloud-providers)
- [Bare Metal](#bare-metal)
- [Security](#security)
- [Scaling](#scaling)
- [Backup & Recovery](#backup--recovery)
- [Troubleshooting](#troubleshooting)

---

## Overview

The JuraGPT Auditor is designed for production deployment with multiple deployment options. Choose based on your infrastructure and requirements.

### Quick Comparison

| Option | Complexity | Scalability | Cost | Best For |
|--------|------------|-------------|------|----------|
| **Docker Compose** | Low | Limited | Low | Development, small deployments |
| **Kubernetes** | High | Excellent | Medium-High | Production, large scale |
| **Cloud Services** | Medium | Excellent | Variable | Managed infrastructure |
| **Bare Metal** | Medium | Manual | Low | Custom infrastructure |

---

## Deployment Options

### Option 1: Docker Compose ✅ RECOMMENDED for Getting Started

**Pros:**
- Simple setup (3 commands)
- All-in-one stack (API + DB + Monitoring)
- Easy local development
- Good for small-medium deployments

**Cons:**
- Limited horizontal scaling
- Single-host deployment
- Manual updates

**Use When:**
- Getting started
- Development/staging environments
- Small production deployments (< 100 req/s)
- Single-server deployment

### Option 2: Kubernetes ✅ RECOMMENDED for Production

**Pros:**
- Excellent horizontal scaling
- Auto-healing and rolling updates
- Multi-node deployment
- Industry standard

**Cons:**
- Complex setup
- Requires Kubernetes expertise
- Higher resource overhead

**Use When:**
- Large production deployments
- High availability required
- Auto-scaling needed
- Multi-region deployment

### Option 3: Cloud Services

**Pros:**
- Managed infrastructure
- Built-in scaling
- Reduced operational burden

**Cons:**
- Vendor lock-in
- Higher cost
- Less control

**Use When:**
- Prefer managed services
- Fast time-to-market
- Cloud-first strategy

### Option 4: Bare Metal

**Pros:**
- Full control
- No containerization overhead
- Customizable

**Cons:**
- Manual configuration
- Complex dependency management
- Harder to scale

**Use When:**
- Existing infrastructure
- Specific hardware requirements
- Maximum control needed

---

## Docker Compose

### Quick Start

```bash
# Clone repository
git clone https://github.com/yourusername/auditor.git
cd auditor

# Configure environment
cp .env.example .env
# Edit .env with your settings

# Start services
docker-compose up -d

# Verify
docker-compose ps
curl http://localhost:8888/health
```

**Access:**
- API: http://localhost:8888
- API Docs: http://localhost:8888/docs
- Grafana: http://localhost:3333 (admin/admin)
- Prometheus: http://localhost:9090

### Production Configuration

**1. Update Environment Variables**

Edit `.env`:

```bash
# PostgreSQL
POSTGRES_PASSWORD=STRONG_PASSWORD_HERE

# Grafana
GRAFANA_PASSWORD=STRONG_PASSWORD_HERE

# Logging
LOG_LEVEL=INFO

# Performance
CACHE_SIZE=5000
BATCH_SIZE=64
```

**2. Configure Resource Limits**

Edit `docker-compose.yml`:

```yaml
services:
  auditor-api:
    deploy:
      resources:
        limits:
          cpus: '4'
          memory: 8G
        reservations:
          cpus: '2'
          memory: 4G
```

**3. Enable TLS**

Use nginx or Traefik reverse proxy:

```yaml
services:
  nginx:
    image: nginx:alpine
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./ssl:/etc/nginx/ssl:ro
    ports:
      - "443:443"
    depends_on:
      - auditor-api
```

**4. Persistent Volumes**

Ensure volumes are backed up:

```bash
# Backup PostgreSQL
docker exec auditor-postgres pg_dump -U auditor auditor > backup.sql

# Backup Prometheus data
docker run --rm -v auditor_prometheus-data:/data \
  -v $(pwd)/backup:/backup \
  alpine tar czf /backup/prometheus.tar.gz /data
```

### Scaling with Docker Compose

```bash
# Scale API horizontally
docker-compose up -d --scale auditor-api=3

# Add load balancer (nginx)
docker-compose -f docker-compose.yml -f docker-compose.lb.yml up -d
```

---

## Kubernetes

### Prerequisites

- Kubernetes cluster (1.20+)
- kubectl configured
- Helm 3.x installed
- Persistent volume provisioner

### Helm Chart Deployment

**1. Add Helm Repository** (when available)

```bash
helm repo add juragpt https://charts.juragpt.example.com
helm repo update
```

**2. Install with Helm**

```bash
# Create namespace
kubectl create namespace auditor

# Install chart
helm install auditor juragpt/auditor \
  --namespace auditor \
  --set postgresql.password=STRONG_PASSWORD \
  --set replicaCount=3 \
  --set autoscaling.enabled=true \
  --set ingress.enabled=true \
  --set ingress.host=auditor.example.com
```

**3. Verify Deployment**

```bash
# Check pods
kubectl get pods -n auditor

# Check services
kubectl get svc -n auditor

# Check ingress
kubectl get ingress -n auditor

# Test API
kubectl port-forward -n auditor svc/auditor-api 8888:8000
curl http://localhost:8888/health
```

### Manual Kubernetes Deployment

**Deployment Configuration** (`k8s/deployment.yaml`):

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: auditor-api
  namespace: auditor
spec:
  replicas: 3
  selector:
    matchLabels:
      app: auditor-api
  template:
    metadata:
      labels:
        app: auditor-api
    spec:
      containers:
      - name: auditor-api
        image: juragpt-auditor:latest
        ports:
        - containerPort: 8000
          name: http
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: auditor-secrets
              key: database-url
        - name: LOG_LEVEL
          value: "INFO"
        resources:
          requests:
            memory: "4Gi"
            cpu: "2"
          limits:
            memory: "8Gi"
            cpu: "4"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 60
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
```

**Service Configuration** (`k8s/service.yaml`):

```yaml
apiVersion: v1
kind: Service
metadata:
  name: auditor-api
  namespace: auditor
spec:
  selector:
    app: auditor-api
  ports:
  - port: 8000
    targetPort: 8000
    name: http
  type: ClusterIP
```

**Ingress Configuration** (`k8s/ingress.yaml`):

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: auditor-ingress
  namespace: auditor
  annotations:
    cert-manager.io/cluster-issuer: "letsencrypt-prod"
spec:
  ingressClassName: nginx
  tls:
  - hosts:
    - auditor.example.com
    secretName: auditor-tls
  rules:
  - host: auditor.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: auditor-api
            port:
              number: 8000
```

**Horizontal Pod Autoscaler** (`k8s/hpa.yaml`):

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: auditor-api-hpa
  namespace: auditor
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: auditor-api
  minReplicas: 3
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

**Deploy:**

```bash
kubectl apply -f k8s/
```

### PostgreSQL on Kubernetes

**Option 1: Managed Database** (Recommended)

Use cloud provider's managed PostgreSQL:
- AWS RDS
- Google Cloud SQL
- Azure Database for PostgreSQL

**Option 2: PostgreSQL Operator**

```bash
# Install Zalando PostgreSQL Operator
helm install postgres-operator postgres-operator/postgres-operator

# Create cluster
kubectl apply -f - <<EOF
apiVersion: "acid.zalan.do/v1"
kind: postgresql
metadata:
  name: auditor-postgres
  namespace: auditor
spec:
  teamId: "auditor"
  volume:
    size: 100Gi
  numberOfInstances: 3
  postgresql:
    version: "15"
EOF
```

### Monitoring on Kubernetes

**Install Prometheus Stack:**

```bash
helm install prometheus prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --create-namespace \
  --set prometheus.prometheusSpec.serviceMonitorSelectorNilUsesHelmValues=false
```

**ServiceMonitor for Auditor:**

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: auditor-api
  namespace: auditor
spec:
  selector:
    matchLabels:
      app: auditor-api
  endpoints:
  - port: http
    path: /metrics
    interval: 10s
```

---

## Cloud Providers

### AWS (Amazon Web Services)

**Architecture:**

```
┌─────────────────────────────────────────┐
│          Application Load Balancer      │
│              (HTTPS/TLS)                │
└────────────────┬────────────────────────┘
                 │
    ┌────────────┼────────────┐
    │            │            │
    ▼            ▼            ▼
┌────────┐  ┌────────┐  ┌────────┐
│  ECS    │  │  ECS    │  │  ECS    │
│ Task 1  │  │ Task 2  │  │ Task 3  │
└────┬───┘  └────┬───┘  └────┬───┘
     │           │           │
     └───────────┼───────────┘
                 │
         ┌───────▼───────┐
         │   RDS          │
         │ PostgreSQL    │
         └───────────────┘
```

**Deployment Steps:**

1. **Create ECR Repository**:

```bash
aws ecr create-repository --repository-name juragpt-auditor
```

2. **Build and Push Image**:

```bash
# Authenticate
aws ecr get-login-password | docker login --username AWS --password-stdin $ECR_URL

# Build
docker build -t juragpt-auditor:latest .

# Tag
docker tag juragpt-auditor:latest $ECR_URL/juragpt-auditor:latest

# Push
docker push $ECR_URL/juragpt-auditor:latest
```

3. **Create RDS Instance**:

```bash
aws rds create-db-instance \
  --db-instance-identifier auditor-db \
  --db-instance-class db.t3.medium \
  --engine postgres \
  --engine-version 15.3 \
  --master-username auditor \
  --master-user-password STRONG_PASSWORD \
  --allocated-storage 100
```

4. **Create ECS Task Definition** (`task-definition.json`):

```json
{
  "family": "auditor-api",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "2048",
  "memory": "4096",
  "containerDefinitions": [
    {
      "name": "auditor-api",
      "image": "$ECR_URL/juragpt-auditor:latest",
      "portMappings": [
        {
          "containerPort": 8000,
          "protocol": "tcp"
        }
      ],
      "environment": [
        {
          "name": "DATABASE_URL",
          "value": "postgresql://auditor:PASSWORD@RDS_ENDPOINT:5432/auditor"
        },
        {
          "name": "LOG_LEVEL",
          "value": "INFO"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/auditor-api",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "ecs"
        }
      }
    }
  ]
}
```

5. **Create ECS Service**:

```bash
aws ecs create-service \
  --cluster auditor-cluster \
  --service-name auditor-api \
  --task-definition auditor-api \
  --desired-count 3 \
  --launch-type FARGATE \
  --load-balancers targetGroupArn=$TARGET_GROUP_ARN,containerName=auditor-api,containerPort=8000
```

### Google Cloud Platform (GCP)

**Deployment with Cloud Run:**

```bash
# Build and push to GCR
gcloud builds submit --tag gcr.io/PROJECT_ID/auditor-api

# Deploy to Cloud Run
gcloud run deploy auditor-api \
  --image gcr.io/PROJECT_ID/auditor-api \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars DATABASE_URL=$DB_URL \
  --memory 4Gi \
  --cpu 2 \
  --min-instances 1 \
  --max-instances 10
```

**With GKE (Google Kubernetes Engine):**

```bash
# Create cluster
gcloud container clusters create auditor-cluster \
  --num-nodes 3 \
  --machine-type n1-standard-4 \
  --enable-autoscaling \
  --min-nodes 3 \
  --max-nodes 10

# Deploy (use Kubernetes steps above)
kubectl apply -f k8s/
```

### Azure

**Deployment with Azure Container Instances:**

```bash
# Create resource group
az group create --name auditor-rg --location eastus

# Create container registry
az acr create --resource-group auditor-rg \
  --name auditoracr --sku Basic

# Build and push
az acr build --registry auditoracr \
  --image auditor-api:latest .

# Create PostgreSQL
az postgres server create \
  --resource-group auditor-rg \
  --name auditor-db \
  --sku-name B_Gen5_1 \
  --storage-size 51200

# Create container instance
az container create \
  --resource-group auditor-rg \
  --name auditor-api \
  --image auditoracr.azurecr.io/auditor-api:latest \
  --cpu 2 \
  --memory 4 \
  --ports 8000 \
  --environment-variables \
    DATABASE_URL=$DB_URL \
    LOG_LEVEL=INFO
```

---

## Bare Metal

### System Requirements

**Minimum**:
- 2 CPU cores
- 4 GB RAM
- 20 GB disk space
- Ubuntu 20.04+ / Debian 11+ / CentOS 8+
- Python 3.11+
- PostgreSQL 15+

**Recommended** (Production):
- 4-8 CPU cores
- 8-16 GB RAM
- 100 GB SSD
- Load balancer (nginx/HAProxy)

### Installation Steps

**1. Install System Dependencies**:

```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y \
  python3.11 \
  python3.11-dev \
  python3.11-venv \
  postgresql \
  postgresql-contrib \
  nginx \
  supervisor

# CentOS/RHEL
sudo dnf install -y \
  python3.11 \
  python3.11-devel \
  postgresql15-server \
  nginx \
  supervisor
```

**2. Setup PostgreSQL**:

```bash
# Create user and database
sudo -u postgres psql <<EOF
CREATE USER auditor WITH PASSWORD 'STRONG_PASSWORD';
CREATE DATABASE auditor OWNER auditor;
GRANT ALL PRIVILEGES ON DATABASE auditor TO auditor;
EOF
```

**3. Install Application**:

```bash
# Create user
sudo useradd -m -s /bin/bash auditor

# Clone repository
sudo -u auditor git clone https://github.com/yourusername/auditor.git /home/auditor/app
cd /home/auditor/app

# Create virtual environment
sudo -u auditor python3.11 -m venv venv
sudo -u auditor venv/bin/pip install -e ".[postgres]"

# Download models
sudo -u auditor venv/bin/python -m spacy download de_core_news_md
```

**4. Configure Application**:

Create `/home/auditor/app/.env`:

```bash
DATABASE_URL=postgresql://auditor:STRONG_PASSWORD@localhost:5432/auditor
LOG_LEVEL=INFO
CACHE_SIZE=5000
```

**5. Setup Supervisor** (Process Manager):

Create `/etc/supervisor/conf.d/auditor.conf`:

```ini
[program:auditor-api]
command=/home/auditor/app/venv/bin/gunicorn auditor.api.server:app \
  -w 4 \
  -k uvicorn.workers.UvicornWorker \
  --bind 127.0.0.1:8000 \
  --access-logfile - \
  --error-logfile -
directory=/home/auditor/app
user=auditor
autostart=true
autorestart=true
stdout_logfile=/var/log/auditor/access.log
stderr_logfile=/var/log/auditor/error.log
```

**6. Setup Nginx** (Reverse Proxy):

Create `/etc/nginx/sites-available/auditor`:

```nginx
upstream auditor_backend {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name auditor.example.com;

    # Redirect to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name auditor.example.com;

    ssl_certificate /etc/letsencrypt/live/auditor.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/auditor.example.com/privkey.pem;

    client_max_body_size 10M;

    location / {
        proxy_pass http://auditor_backend;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Health check (no auth)
    location /health {
        proxy_pass http://auditor_backend;
        access_log off;
    }
}
```

**7. Start Services**:

```bash
# Enable and start
sudo systemctl enable supervisor
sudo systemctl start supervisor

sudo systemctl enable nginx
sudo systemctl start nginx

# Verify
curl http://localhost:8000/health
curl https://auditor.example.com/health
```

---

## Security

### TLS/SSL

**Let's Encrypt (Free)**:

```bash
# Install certbot
sudo apt-get install certbot python3-certbot-nginx

# Obtain certificate
sudo certbot --nginx -d auditor.example.com

# Auto-renewal
sudo certbot renew --dry-run
```

### Firewall

```bash
# UFW (Ubuntu)
sudo ufw allow 22/tcp  # SSH
sudo ufw allow 80/tcp  # HTTP
sudo ufw allow 443/tcp # HTTPS
sudo ufw enable

# iptables
sudo iptables -A INPUT -p tcp --dport 22 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 80 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 443 -j ACCEPT
sudo iptables -A INPUT -j DROP
```

### Secrets Management

**Environment Variables**:
```bash
# Never commit .env to version control
echo ".env" >> .gitignore

# Use strong passwords
openssl rand -base64 32
```

**Kubernetes Secrets**:
```bash
kubectl create secret generic auditor-secrets \
  --from-literal=database-url=$DB_URL \
  --namespace auditor
```

**AWS Secrets Manager**:
```bash
aws secretsmanager create-secret \
  --name auditor/database-url \
  --secret-string $DB_URL
```

---

## Scaling

### Horizontal Scaling

**Docker Compose**:
```bash
docker-compose up -d --scale auditor-api=5
```

**Kubernetes**:
```bash
kubectl scale deployment auditor-api --replicas=10 -n auditor
```

**Auto-scaling (Kubernetes HPA)**:
- Automatically scales based on CPU/memory
- See HPA configuration above

### Vertical Scaling

**Increase Resources**:
- CPU: Add more cores
- Memory: Increase RAM (8GB → 16GB)
- GPU: Add GPU for faster embeddings

### Database Scaling

**Read Replicas**:
```sql
-- PostgreSQL streaming replication
-- Primary: Allow connections from replicas
-- Replica: Connect to primary for replication
```

**Connection Pooling** (PgBouncer):
```bash
# Install PgBouncer
sudo apt-get install pgbouncer

# Configure
# /etc/pgbouncer/pgbouncer.ini
[databases]
auditor = host=localhost port=5432 dbname=auditor

[pgbouncer]
listen_addr = 127.0.0.1
listen_port = 6432
pool_mode = transaction
max_client_conn = 1000
default_pool_size = 25
```

---

## Backup & Recovery

### Database Backups

**Automated Backups** (cron):

```bash
#!/bin/bash
# /usr/local/bin/backup-auditor-db.sh

BACKUP_DIR="/backups/auditor"
DATE=$(date +%Y%m%d_%H%M%S)

# Create backup
pg_dump -U auditor auditor | gzip > $BACKUP_DIR/auditor_$DATE.sql.gz

# Keep only last 30 days
find $BACKUP_DIR -name "auditor_*.sql.gz" -mtime +30 -delete
```

**Crontab**:
```bash
# Daily at 2 AM
0 2 * * * /usr/local/bin/backup-auditor-db.sh
```

### Restore

```bash
# Restore from backup
gunzip -c backup.sql.gz | psql -U auditor auditor
```

### Disaster Recovery

**1. Document your setup**:
- Infrastructure configuration
- Environment variables
- DNS settings

**2. Test recovery**:
- Regularly test restoring from backups
- Practice deployment from scratch

**3. Off-site backups**:
- Store backups in S3/GCS
- Geographic redundancy

---

## Troubleshooting

### Common Issues

**Issue: API not starting**

```bash
# Check logs
docker logs auditor-api
# or
sudo journalctl -u supervisor -f

# Common causes:
# - Database not reachable
# - Missing environment variables
# - Port already in use
```

**Issue: High latency**

```bash
# Check resource usage
docker stats auditor-api

# Check database
psql -U auditor -d auditor -c "SELECT * FROM pg_stat_activity;"

# Check cache hit rate
curl http://localhost:8888/metrics | grep cache
```

**Issue: Out of memory**

```bash
# Reduce cache size
# In .env:
CACHE_SIZE=1000  # Reduce from 5000

# Restart
docker-compose restart auditor-api
```

---

## Health Checks

**Docker Compose Health Check**:
```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 60s
```

**Kubernetes Probes**:
```yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 60
  periodSeconds: 30

readinessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 30
  periodSeconds: 10
```

---

## Support

- **Documentation**: [docs/](.)
- **Issues**: [GitHub Issues](https://github.com/yourusername/auditor/issues)
- **Deployment Help**: [GitHub Discussions](https://github.com/yourusername/auditor/discussions)

---

**Built with ❤️ by the JuraGPT Team**
