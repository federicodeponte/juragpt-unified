# Monitoring Guide

Comprehensive guide to monitoring the JuraGPT Auditor verification service.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Metrics Reference](#metrics-reference)
- [Dashboards](#dashboards)
- [Alert Runbook](#alert-runbook)
- [Troubleshooting](#troubleshooting)
- [Production Best Practices](#production-best-practices)

---

## Overview

The JuraGPT Auditor includes a comprehensive monitoring stack based on **Prometheus** for metrics collection and **Grafana** for visualization and alerting.

### Monitoring Stack Components

| Component | Purpose | Port | Access |
|-----------|---------|------|--------|
| **Prometheus** | Time-series metrics database | 9090 | http://localhost:9090 |
| **Grafana** | Dashboards and visualization | 3333 | http://localhost:3333 |
| **API Metrics Endpoint** | Application metrics | 8888 | http://localhost:8888/metrics |

**Default Credentials:**
- **Grafana**: username `admin`, password `admin` (change in production!)

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     Auditor API (FastAPI)                    │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ Verification │  │  Confidence  │  │   Storage    │     │
│  │   Endpoint   │  │    Engine    │  │  Interface   │     │
│  └───────┬──────┘  └───────┬──────┘  └───────┬──────┘     │
│          │                 │                 │              │
│          └─────────────────┴─────────────────┘              │
│                           │                                 │
│                  ┌────────▼────────┐                        │
│                  │ Prometheus      │                        │
│                  │ Client Library  │                        │
│                  │ (metrics)       │                        │
│                  └────────┬────────┘                        │
└───────────────────────────┼──────────────────────────────────┘
                            │
                   /metrics endpoint
                            │
                ┌───────────▼────────────┐
                │    Prometheus Server   │
                │  - Scrapes /metrics    │
                │  - Stores time-series  │
                │  - Evaluates alerts    │
                └───────────┬────────────┘
                            │
                     PromQL queries
                            │
                ┌───────────▼────────────┐
                │       Grafana          │
                │  - Visualizes metrics  │
                │  - Displays dashboards │
                │  - Sends alerts        │
                └────────────────────────┘
```

---

## Quick Start

### 1. Start the Monitoring Stack

```bash
# Start all services including monitoring
docker-compose up -d

# Verify all services are running
docker-compose ps

# Check Prometheus status
curl http://localhost:9090/-/healthy

# Check Grafana status
curl http://localhost:3333/api/health
```

### 2. Access the Dashboards

1. **Open Grafana**: http://localhost:3333
2. **Login**: admin / admin (change password when prompted)
3. **Navigate to**: Dashboards → JuraGPT Auditor - Overview

### 3. Verify Metrics Collection

```bash
# Check raw metrics from API
curl http://localhost:8888/metrics

# Query Prometheus
curl 'http://localhost:9090/api/v1/query?query=up{job="auditor-api"}'
```

---

## Metrics Reference

### Core Application Metrics

#### Request Metrics

| Metric Name | Type | Description | Labels |
|-------------|------|-------------|--------|
| `auditor_verify_requests_total` | Counter | Total verification requests | `status`, `trust_label` |
| `auditor_verify_latency_seconds` | Histogram | Request latency distribution | - |
| `auditor_verify_in_progress` | Gauge | Active verification requests | - |

**Example PromQL:**
```promql
# Request rate (requests per second)
rate(auditor_verify_requests_total[5m])

# P95 latency
histogram_quantile(0.95, rate(auditor_verify_latency_seconds_bucket[5m]))

# Error rate
rate(auditor_verify_requests_total{status="error"}[5m]) /
  rate(auditor_verify_requests_total[5m])
```

#### Confidence Metrics

| Metric Name | Type | Description | Labels |
|-------------|------|-------------|--------|
| `auditor_confidence_score` | Histogram | Confidence score distribution | - |
| `auditor_confidence_score_sum` | Counter | Sum of confidence scores | - |
| `auditor_confidence_score_count` | Counter | Count of confidence scores | - |
| `auditor_low_confidence_requests_total` | Counter | Requests with low confidence | `threshold` |

**Example PromQL:**
```promql
# Average confidence score
auditor_confidence_score_sum / auditor_confidence_score_count

# Percentage of low-confidence verifications
rate(auditor_low_confidence_requests_total[15m]) /
  rate(auditor_confidence_score_count[15m])
```

#### Source Processing Metrics

| Metric Name | Type | Description | Labels |
|-------------|------|-------------|--------|
| `auditor_sources_processed_total` | Counter | Total sources processed | `source_type` |
| `auditor_citations_extracted_total` | Counter | Total citations found | - |
| `auditor_source_processing_seconds` | Histogram | Source processing time | - |

#### Cache Metrics

| Metric Name | Type | Description | Labels |
|-------------|------|-------------|--------|
| `auditor_cache_hits_total` | Counter | Embedding cache hits | - |
| `auditor_cache_misses_total` | Counter | Embedding cache misses | - |
| `auditor_cache_size_bytes` | Gauge | Cache memory usage | - |

**Example PromQL:**
```promql
# Cache hit rate
rate(auditor_cache_hits_total[10m]) /
  (rate(auditor_cache_hits_total[10m]) + rate(auditor_cache_misses_total[10m]))
```

### System Metrics

| Metric Name | Type | Description |
|-------------|------|-------------|
| `process_cpu_seconds_total` | Counter | CPU time used |
| `process_resident_memory_bytes` | Gauge | Memory usage (RSS) |
| `process_open_fds` | Gauge | Open file descriptors |

---

## Dashboards

### JuraGPT Auditor - Overview Dashboard

The main dashboard provides a comprehensive view of system health and performance.

#### Top Row - Key Performance Indicators (KPIs)

**Panel 1: Requests/Min**
- **Metric**: `rate(auditor_verify_requests_total[5m]) * 60`
- **Purpose**: Monitor API traffic volume
- **Normal**: 1-100 requests/min (depending on load)
- **Alert if**: Sudden spike or drop

**Panel 2: P95 Latency**
- **Metric**: `histogram_quantile(0.95, rate(auditor_verify_latency_seconds_bucket[5m])) * 1000`
- **Purpose**: Track user-facing performance
- **Target**: < 800ms
- **Thresholds**: Yellow at 500ms, Red at 800ms

**Panel 3: Average Confidence**
- **Metric**: `avg(auditor_confidence_score_sum / auditor_confidence_score_count)`
- **Purpose**: Monitor verification quality
- **Target**: > 0.8
- **Thresholds**: Red < 0.6, Yellow 0.6-0.8, Green > 0.8

**Panel 4: Service Status**
- **Metric**: `up{job="auditor-api"}`
- **Purpose**: Service availability check
- **Values**: UP (1) or DOWN (0)

#### Middle Row - Time Series Trends

**Panel 5: Request Rate Over Time**
- **Metrics**:
  - Total: `rate(auditor_verify_requests_total[5m])`
  - Successful: `rate(auditor_verify_requests_total{status="success"}[5m])`
  - Errors: `rate(auditor_verify_requests_total{status="error"}[5m])`
- **Purpose**: Identify traffic patterns and error spikes

**Panel 6: Latency Percentiles**
- **Metrics**:
  - P50: `histogram_quantile(0.50, rate(auditor_verify_latency_seconds_bucket[5m]))`
  - P95: `histogram_quantile(0.95, rate(auditor_verify_latency_seconds_bucket[5m]))`
  - P99: `histogram_quantile(0.99, rate(auditor_verify_latency_seconds_bucket[5m]))`
- **Purpose**: Understand latency distribution

#### Bottom Row - Quality & Distribution

**Panel 7: Trust Label Distribution (1h)**
- **Metrics**:
  - Verified: `sum(increase(auditor_verify_requests_total{trust_label=~".*Verified"}[1h]))`
  - Review: `sum(increase(auditor_verify_requests_total{trust_label=~".*Review"}[1h]))`
  - Rejected: `sum(increase(auditor_verify_requests_total{trust_label=~".*Rejected"}[1h]))`
- **Purpose**: Monitor output quality distribution

**Panel 8: Confidence Score Distribution**
- **Metric**: `sum(rate(auditor_confidence_score_bucket[5m])) by (le)`
- **Purpose**: Identify low-confidence patterns

### Creating Custom Dashboards

1. **Open Grafana**: http://localhost:3333
2. **Click**: + → Dashboard → Add visualization
3. **Select**: Prometheus as data source
4. **Enter PromQL query** (see metrics reference above)
5. **Configure**: Panel title, visualization type, thresholds
6. **Save dashboard**

---

## Alert Runbook

### Availability Alerts

#### Alert: `AuditorServiceDown`

**Severity**: Critical
**Trigger**: `up{job="auditor-api"} == 0` for 1 minute

**Symptoms:**
- API not responding to health checks
- Users cannot access verification service
- Metrics endpoint unavailable

**Investigation:**
```bash
# Check container status
docker-compose ps

# Check API logs
docker logs auditor-api --tail 100

# Check health endpoint
curl http://localhost:8888/health
```

**Resolution:**
1. Check if container is running: `docker-compose ps auditor-api`
2. If stopped, restart: `docker-compose restart auditor-api`
3. If crashing, check logs for errors
4. Common issues:
   - Database connection failure → Check postgres container
   - Model loading error → Check model cache volume
   - Configuration error → Verify environment variables

**Escalation**: If restart doesn't resolve, check database and dependency health.

---

### Performance Alerts

#### Alert: `HighLatencyP95`

**Severity**: Warning
**Trigger**: `histogram_quantile(0.95, rate(auditor_verify_latency_seconds_bucket[5m])) > 0.8` for 5 minutes

**Symptoms:**
- Users experiencing slow response times
- P95 latency > 800ms
- Increased request timeouts

**Investigation:**
```bash
# Check CPU/memory usage
docker stats auditor-api

# Check database performance
docker logs auditor-postgres | grep "slow query"

# Check current load
curl http://localhost:9090/api/v1/query?query=rate(auditor_verify_requests_total[1m])
```

**Resolution:**
1. **Check resource usage**:
   - High CPU → Consider scaling or optimizing embeddings
   - High memory → Check for memory leaks, review cache size
2. **Check database**:
   - Slow queries → Add indexes
   - Connection pool exhausted → Increase pool size
3. **Check embedding cache**:
   - Low hit rate → Increase cache size
4. **Scale if needed**:
   - Add more API replicas
   - Increase container resources

**Prevention**: Monitor trends, scale proactively during peak hours.

#### Alert: `HighLatencyP99`

**Severity**: Critical
**Trigger**: `histogram_quantile(0.99, rate(auditor_verify_latency_seconds_bucket[5m])) > 2.0` for 5 minutes

**Symptoms:**
- Severe performance degradation
- P99 latency > 2 seconds
- Some requests timing out

**Investigation:** Same as HighLatencyP95, plus:
```bash
# Check for long-running requests
# Check model loading (first request after restart is slow)
docker logs auditor-api | grep "Model loaded"
```

**Resolution:** Immediate investigation required. Likely causes:
- Model not cached → Check volume mounts
- Database overload → Scale database
- Memory pressure → Increase container memory limit

---

### Error Rate Alerts

#### Alert: `HighErrorRate`

**Severity**: Warning
**Trigger**: Error rate > 5% for 5 minutes

**Symptoms:**
- Users seeing error responses
- Error rate > 5%
- Increased 5xx status codes

**Investigation:**
```bash
# Check error logs
docker logs auditor-api --tail 200 | grep ERROR

# Check error types
curl http://localhost:8888/metrics | grep error

# Check database connectivity
docker-compose exec postgres psql -U auditor -d auditor -c "\conninfo"
```

**Common Errors:**
- **Database errors**: Connection pool exhausted, query timeouts
- **Model errors**: Out of memory, CUDA errors (if using GPU)
- **Validation errors**: Bad input data from clients
- **Configuration errors**: Missing API keys, invalid settings

**Resolution:**
1. Group errors by type from logs
2. Fix root cause (see common errors above)
3. If client errors (4xx), document proper API usage
4. If server errors (5xx), fix application bugs

#### Alert: `CriticalErrorRate`

**Severity**: Critical
**Trigger**: Error rate > 25% for 2 minutes

**Symptoms:**
- System mostly failing
- Over 25% of requests failing

**Resolution:**
1. **Immediate**: Consider rolling back recent deployment
2. **Check**: Recent configuration changes
3. **Investigate**: Critical failures in logs
4. **Escalate**: If cause not immediately apparent

---

### Quality Alerts

#### Alert: `LowConfidenceRate`

**Severity**: Warning
**Trigger**: > 30% of verifications have confidence < 0.6 for 15 minutes

**Symptoms:**
- High rate of low-confidence verifications
- Increased "Review Required" labels
- Quality degradation

**Investigation:**
```bash
# Check confidence distribution
curl 'http://localhost:9090/api/v1/query?query=rate(auditor_confidence_score_bucket[15m])'

# Check source quality
docker logs auditor-api | grep "source quality"
```

**Possible Causes:**
- **Poor source quality**: Sources don't match answers well
- **Model drift**: Embedding model performing poorly
- **Configuration**: Thresholds set incorrectly
- **Input quality**: Answer quality degraded

**Resolution:**
1. Review recent source uploads for quality
2. Check if answers align with sources
3. Verify model is loaded correctly
4. Review threshold configuration
5. Consider retraining or updating models

#### Alert: `VeryLowConfidenceSpike`

**Severity**: Critical
**Trigger**: > 15% of verifications have confidence < 0.4 for 5 minutes

**Symptoms:**
- Sudden spike in very low confidence
- Potential model failure

**Investigation:**
```bash
# Check if model loaded correctly
docker logs auditor-api | grep -A 10 "Loading model"

# Check for recent config changes
git log --oneline -10
```

**Resolution:**
1. **Verify model loading**: Check logs for model initialization
2. **Check data quality**: Sudden change in input data?
3. **Restart if needed**: Model may have corrupted state
4. **Rollback**: If after recent deployment

---

### Resource Alerts

#### Alert: `HighMemoryUsage`

**Severity**: Warning
**Trigger**: Memory usage > 85% of limit for 5 minutes

**Investigation:**
```bash
# Check memory usage
docker stats auditor-api --no-stream

# Check cache size
curl http://localhost:8888/metrics | grep cache_size
```

**Resolution:**
1. **Reduce cache size**: Adjust `CACHE_SIZE` environment variable
2. **Check for leaks**: Restart container, monitor growth
3. **Increase limit**: If legitimate usage, increase container memory
4. **Scale horizontally**: Add more API instances

#### Alert: `NearMemoryLimit`

**Severity**: Critical
**Trigger**: Memory usage > 95% of limit for 2 minutes

**Symptoms:**
- Container at risk of being killed (OOM)
- Performance degradation

**Resolution:**
1. **Immediate**: Increase memory limit
2. **Or restart**: Free up memory temporarily
3. **Investigate**: Find memory leak or excessive usage
4. **Long-term**: Optimize memory usage or scale

---

### Database Alerts

#### Alert: `DatabaseConnectionFailed`

**Severity**: Critical
**Trigger**: `up{job="postgres"} == 0` for 1 minute

**Investigation:**
```bash
# Check postgres container
docker-compose ps postgres

# Check postgres logs
docker logs auditor-postgres --tail 50

# Try connecting
docker-compose exec postgres psql -U auditor -d auditor
```

**Resolution:**
1. Check container status
2. Restart if needed: `docker-compose restart postgres`
3. Check for disk space issues
4. Verify network connectivity between containers

---

### SLA Alerts

#### Alert: `SLAViolation`

**Severity**: Warning
**Trigger**: P95 latency > 800ms OR error rate > 5% for 10 minutes

**Purpose**: Overall SLA compliance monitoring

**Resolution**: Follow runbooks for HighLatencyP95 or HighErrorRate depending on which condition triggered.

---

## Troubleshooting

### Prometheus Not Scraping Metrics

**Symptoms:**
- Metrics missing in Prometheus
- Queries return no data
- Dashboard panels show "No data"

**Diagnosis:**
```bash
# Check Prometheus targets
curl http://localhost:9090/api/v1/targets | jq

# Check API metrics endpoint
curl http://localhost:8888/metrics

# Check Prometheus logs
docker logs auditor-prometheus
```

**Solutions:**
1. **Check target configuration**: `monitoring/prometheus/prometheus.yml`
2. **Verify network**: Containers on same network?
3. **Check scrape interval**: May need to wait for first scrape
4. **Restart Prometheus**: `docker-compose restart prometheus`

### Grafana Dashboard Shows No Data

**Symptoms:**
- Panels show "No data"
- Queries return empty results

**Diagnosis:**
```bash
# Test PromQL query directly in Prometheus
curl 'http://localhost:9090/api/v1/query?query=up'

# Check Grafana datasource
curl -u admin:admin http://localhost:3333/api/datasources
```

**Solutions:**
1. **Verify datasource**: Grafana → Configuration → Data Sources
2. **Check Prometheus URL**: Should be `http://prometheus:9090`
3. **Test query in Prometheus UI**: http://localhost:9090/graph
4. **Check time range**: Select "Last 1 hour" in Grafana
5. **Generate traffic**: Make API requests to generate metrics

### High Latency for First Request

**Symptoms:**
- First request after startup takes 10-30 seconds
- Subsequent requests are fast

**Cause:** Model loading on first use (lazy loading).

**Solutions:**
1. **Pre-warm models**: Add startup script to load models
2. **Accept behavior**: Document it as expected
3. **Health check warmup**: Configure health check with initial delay

### Metrics Missing After Restart

**Symptoms:**
- Historical data lost after restart
- Metrics reset to zero

**Cause:** Prometheus data not persisted.

**Solutions:**
1. **Check volume**: `docker volume inspect auditor_prometheus-data`
2. **Verify mount**: In `docker-compose.yml`, ensure volume mounted correctly
3. **Retention policy**: Check `--storage.tsdb.retention.time` setting

---

## Production Best Practices

### 1. Alert Configuration

**Configure Alertmanager** for production alerting:

```yaml
# monitoring/prometheus/alertmanager.yml
global:
  resolve_timeout: 5m

route:
  receiver: 'team-email'
  group_by: ['alertname', 'severity']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h

receivers:
  - name: 'team-email'
    email_configs:
      - to: 'oncall@yourcompany.com'
        from: 'prometheus@yourcompany.com'
        smarthost: 'smtp.yourcompany.com:587'
```

Enable in `docker-compose.yml`:
```yaml
alertmanager:
  image: prom/alertmanager:latest
  volumes:
    - ./monitoring/prometheus/alertmanager.yml:/etc/alertmanager/alertmanager.yml
  ports:
    - "9093:9093"
```

### 2. Data Retention

**Adjust retention based on needs:**

```yaml
# docker-compose.yml
prometheus:
  command:
    - '--storage.tsdb.retention.time=30d'  # Keep 30 days
    - '--storage.tsdb.retention.size=50GB' # Max 50GB
```

**Consider long-term storage** with Thanos or Victoria Metrics for > 30 days.

### 3. Security

**Enable authentication:**

```yaml
# monitoring/grafana/grafana.ini
[auth]
disable_login_form = false
disable_signout_menu = false

[auth.basic]
enabled = true

[security]
admin_user = admin
admin_password = ${GRAFANA_ADMIN_PASSWORD}
secret_key = ${GRAFANA_SECRET_KEY}
```

**Restrict access:**
- Use firewall rules to limit Prometheus/Grafana access
- Enable HTTPS with reverse proxy (nginx/Traefik)
- Use API keys for programmatic access

### 4. High Availability

**For production deployments:**

1. **Multiple Prometheus instances** with identical configuration
2. **Prometheus federation** to aggregate metrics
3. **Load-balanced Grafana** instances
4. **Remote write** to long-term storage

### 5. Backup

**Backup Grafana dashboards:**
```bash
# Export all dashboards
curl -u admin:admin http://localhost:3333/api/search | \
  jq -r '.[] | select(.type == "dash-db") | .uid' | \
  while read uid; do
    curl -u admin:admin "http://localhost:3333/api/dashboards/uid/$uid" | \
    jq > "backup/dashboard-$uid.json"
  done
```

**Backup Prometheus data:**
```bash
# Create snapshot
curl -XPOST http://localhost:9090/api/v1/admin/tsdb/snapshot

# Or use volume backup
docker run --rm -v auditor_prometheus-data:/data \
  -v $(pwd)/backup:/backup \
  alpine tar czf /backup/prometheus-data.tar.gz /data
```

### 6. Performance Tuning

**Optimize scrape intervals:**
```yaml
# For high-traffic services
scrape_configs:
  - job_name: 'auditor-api'
    scrape_interval: 5s  # More frequent

  - job_name: 'postgres'
    scrape_interval: 30s  # Less frequent
```

**Reduce cardinality:**
- Avoid high-cardinality labels (user IDs, timestamps)
- Limit label values
- Use recording rules for frequently queried metrics

### 7. Monitoring the Monitors

**Monitor Prometheus itself:**
```promql
# Prometheus ingestion rate
rate(prometheus_tsdb_head_samples_appended_total[5m])

# Prometheus memory usage
process_resident_memory_bytes{job="prometheus"}

# Rule evaluation duration
prometheus_rule_evaluation_duration_seconds
```

**Set up meta-monitoring** with a separate Prometheus instance.

---

## Additional Resources

- **Prometheus Documentation**: https://prometheus.io/docs/
- **Grafana Documentation**: https://grafana.com/docs/
- **PromQL Basics**: https://prometheus.io/docs/prometheus/latest/querying/basics/
- **Grafana Best Practices**: https://grafana.com/docs/grafana/latest/best-practices/

---

## Support

For issues or questions about monitoring:

1. Check Prometheus logs: `docker logs auditor-prometheus`
2. Check Grafana logs: `docker logs auditor-grafana`
3. Review this guide's troubleshooting section
4. Open an issue on GitHub with:
   - Monitoring stack version
   - Error logs
   - Steps to reproduce
