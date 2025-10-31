# Performance Testing Guide

Comprehensive guide to performance testing, optimization, and troubleshooting for JuraGPT Auditor.

## Table of Contents

- [Overview](#overview)
- [Performance Testing Tools](#performance-testing-tools)
- [Running Performance Tests](#running-performance-tests)
- [Performance Targets](#performance-targets)
- [Optimization Guide](#optimization-guide)
- [Troubleshooting](#troubleshooting)
- [Production Monitoring](#production-monitoring)
- [Best Practices](#best-practices)

---

## Overview

### Why Performance Testing?

Performance testing ensures that Auditor API:

- **Meets SLAs**: Response times under defined limits
- **Handles Load**: Supports expected concurrent users
- **Scales Efficiently**: Performance improves with resources
- **Detects Issues**: Memory leaks, bottlenecks, regressions
- **Validates Changes**: No performance degradation

### Testing Types

| Type | Purpose | Duration | Users | Frequency |
|------|---------|----------|-------|-----------|
| **Smoke Test** | Quick validation | 1 min | 10 | Every deploy |
| **Baseline** | Standard performance | 5 min | 50 | Weekly |
| **Load Test** | Expected load | 15 min | 100-200 | Before release |
| **Stress Test** | Beyond capacity | 10 min | 300-500 | Monthly |
| **Spike Test** | Sudden traffic | 5 min | Spike to 500 | Monthly |
| **Endurance** | Sustained load | 30 min | 100 | Before release |
| **Soak Test** | Memory leaks | 2-24 hours | 75 | Quarterly |

---

## Performance Testing Tools

### 1. Locust - Load Testing

**Purpose**: Simulate realistic user load

**Location**: `tests/performance/locustfile.py`

**Features**:
- Multiple user patterns (standard, burst, heavy)
- Realistic request distribution
- Real-time metrics and graphs
- HTML reports
- Distributed testing support

**Quick Start**:

```bash
# Web UI (http://localhost:8089)
locust -f tests/performance/locustfile.py --host http://localhost:8888

# Headless mode
locust -f tests/performance/locustfile.py \
  --host http://localhost:8888 \
  --headless \
  --users 100 \
  --spawn-rate 10 \
  --run-time 5m \
  --html report.html
```

**Metrics Collected**:
- Requests per second (RPS)
- Response time (p50, p95, p99)
- Error rate
- Request size/response size
- Concurrent users

### 2. Pre-configured Scenarios

**Purpose**: Ready-to-run test scenarios

**Location**: `tests/performance/scenarios.sh`

**Available Scenarios**:

```bash
# Smoke test (quick validation)
./tests/performance/scenarios.sh smoke

# Baseline performance
./tests/performance/scenarios.sh baseline

# Stress test
./tests/performance/scenarios.sh stress

# Spike test
./tests/performance/scenarios.sh spike

# Burst pattern
./tests/performance/scenarios.sh burst

# Heavy requests
./tests/performance/scenarios.sh heavy

# Endurance test
./tests/performance/scenarios.sh endurance

# Soak test (memory leak detection)
./tests/performance/scenarios.sh soak

# Run all
./tests/performance/scenarios.sh all
```

### 3. Performance Benchmarks

**Purpose**: Measure baseline API performance

**Location**: `tests/performance/benchmark.py`

**Benchmarks**:
1. Single request latency
2. Sequential throughput
3. Low concurrency (10 threads)
4. Medium concurrency (25 threads)
5. High concurrency (50 threads)
6. Lightweight requests (1 source)
7. Heavy requests (all sources)

**Usage**:

```bash
# Run all benchmarks
python tests/performance/benchmark.py

# Custom target
python tests/performance/benchmark.py --url http://production:8888

# Save results
python tests/performance/benchmark.py --output results.json
```

**Output**:

```
📊 BENCHMARK SUMMARY
================================================================================

Single Request Latency
  Success Rate: 50/50 (100.0%)
  Throughput:   8.32 req/s
  Latency:
    Min:  95.2ms
    p50:  110.5ms
    p95:  145.8ms
    p99:  162.3ms
    Max:  178.1ms
    Avg:  115.3ms
```

### 4. Memory Profiler

**Purpose**: Detect memory leaks and monitor memory usage

**Location**: `tests/performance/memory_profile.py`

**Metrics**:
- RSS (Resident Set Size) memory
- VMS (Virtual Memory Size)
- Memory growth rate
- Thread count
- File descriptors

**Usage**:

```bash
# Profile for 5 minutes
python tests/performance/memory_profile.py --duration 300

# Generate plot
python tests/performance/memory_profile.py --duration 300 --plot

# Custom interval
python tests/performance/memory_profile.py --interval 10 --duration 600
```

**Output**:

```
📊 MEMORY PROFILE ANALYSIS
============================================================
⏱️  Duration: 300.0s (60 samples)

📈 RSS Memory (Resident Set Size):
   Initial:  485.2 MB
   Final:    512.7 MB
   Min:      482.1 MB
   Max:      520.3 MB
   Average:  498.5 MB
   Growth:   +27.5 MB (+5.7%)

✅ Memory growth is within normal limits
```

---

## Running Performance Tests

### Local Development

**Step 1: Start the API**

```bash
# With Docker
docker-compose up -d auditor-api

# Or locally
python -m auditor.api.server
```

**Step 2: Run Smoke Test**

```bash
./tests/performance/scenarios.sh smoke
```

**Step 3: Run Benchmarks**

```bash
python tests/performance/benchmark.py
```

### Staging Environment

```bash
# Set target host
export LOAD_TEST_HOST=https://staging.example.com

# Run baseline test
./tests/performance/scenarios.sh baseline

# Run stress test
./tests/performance/scenarios.sh stress
```

### Production Environment

⚠️ **Warning**: Always coordinate with operations before load testing production

```bash
# Conservative load test
export LOAD_TEST_HOST=https://api.production.example.com
./tests/performance/scenarios.sh baseline

# Monitor production metrics during test
# Check Prometheus, logs, database connections
```

### Continuous Integration

Add to `.github/workflows/performance.yml`:

```yaml
name: Performance Tests

on:
  push:
    branches: [main]
  schedule:
    - cron: '0 2 * * 0'  # Weekly

jobs:
  performance:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install locust psutil

      - name: Start API server
        run: |
          docker-compose up -d auditor-api
          sleep 30  # Wait for startup

      - name: Run benchmarks
        run: python tests/performance/benchmark.py

      - name: Run smoke test
        run: ./tests/performance/scenarios.sh smoke

      - name: Upload results
        uses: actions/upload-artifact@v3
        with:
          name: performance-results
          path: tests/performance/reports/
```

---

## Performance Targets

### Response Time (Latency)

| Percentile | Target | Acceptable | Poor | Critical |
|------------|--------|------------|------|----------|
| **p50** (median) | < 200ms | < 500ms | < 1000ms | > 1000ms |
| **p95** | < 500ms | < 1000ms | < 2000ms | > 2000ms |
| **p99** | < 1000ms | < 2000ms | < 3000ms | > 3000ms |
| **p99.9** | < 2000ms | < 3000ms | < 5000ms | > 5000ms |

**Rationale**: Most verification requests complete in 100-300ms, p95 under 500ms ensures good user experience.

### Throughput (RPS)

| Concurrency | Target | Acceptable | Poor |
|-------------|--------|------------|------|
| **1** (sequential) | > 10 req/s | > 5 req/s | < 5 req/s |
| **10** (low concurrency) | > 30 req/s | > 20 req/s | < 20 req/s |
| **50** (medium concurrency) | > 50 req/s | > 30 req/s | < 30 req/s |
| **100** (high concurrency) | > 60 req/s | > 40 req/s | < 40 req/s |

**Rationale**: With 4 workers, target is 10-15 req/s per worker. Throughput should scale near-linearly with concurrency up to worker count.

### Error Rate

| Load Level | Target | Acceptable | Poor |
|------------|--------|------------|------|
| **Normal** (< 100 users) | < 0.1% | < 1% | > 1% |
| **High** (100-300 users) | < 1% | < 5% | > 5% |
| **Stress** (> 300 users) | < 5% | < 10% | > 10% |

### Memory Usage

| Metric | Target | Acceptable | Poor |
|--------|--------|------------|------|
| **Initial RSS** | < 500 MB | < 1 GB | > 1 GB |
| **Growth Rate** | < 5 MB/min | < 10 MB/min | > 10 MB/min |
| **Max RSS (1 hour)** | < 1 GB | < 2 GB | > 2 GB |
| **Max RSS (24 hours)** | < 1.5 GB | < 3 GB | > 3 GB |

### CPU Usage

| Scenario | Target | Acceptable | Poor |
|----------|--------|------------|------|
| **Idle** | < 5% | < 10% | > 10% |
| **Normal Load** (50 users) | < 50% | < 75% | > 75% |
| **High Load** (100 users) | < 75% | < 90% | > 90% |

### Database Connections

| Metric | Target | Warning | Critical |
|--------|--------|---------|----------|
| **Active Connections** | < 10 | < 50 | > 80 |
| **Connection Pool Usage** | < 50% | < 80% | > 90% |
| **Wait Time** | < 10ms | < 100ms | > 500ms |

---

## Optimization Guide

### 1. Identify Bottlenecks

**Use profiling tools:**

```bash
# Benchmark to find slow endpoints
python tests/performance/benchmark.py

# Memory profile to find leaks
python tests/performance/memory_profile.py --duration 600 --plot

# Load test to find breaking points
./tests/performance/scenarios.sh stress
```

**Check metrics:**

- Slow endpoint: p95 > 1000ms
- Low throughput: < 20 req/s at 50 concurrent
- High memory: Growth > 10 MB/min
- High CPU: > 80% sustained

### 2. Database Optimization

**Problem**: Slow database queries

**Solutions**:

```python
# Increase connection pool
DB_POOL_SIZE=20
DB_MAX_OVERFLOW=40

# Add indexes
CREATE INDEX idx_verifications_timestamp ON verifications(timestamp);

# Use connection pooling
# PgBouncer in transaction mode
```

**Validation**:

```bash
# Check query times
SELECT query, mean_exec_time, calls
FROM pg_stat_statements
ORDER BY mean_exec_time DESC LIMIT 10;
```

### 3. Worker Configuration

**Problem**: Low throughput, high latency under load

**Solutions**:

```bash
# Increase workers (formula: 2 x CPU cores + 1)
WORKER_COUNT=9  # For 4-core server

# Use uvicorn workers
WORKER_CLASS=uvicorn.workers.UvicornWorker

# Adjust timeouts
REQUEST_TIMEOUT=60
KEEP_ALIVE=5
```

**Validation**:

```bash
# Check worker utilization
ps aux | grep uvicorn

# Load test
./tests/performance/scenarios.sh baseline
```

### 4. Model Optimization

**Problem**: High inference latency

**Solutions**:

```bash
# Use smaller spaCy model
SPACY_MODEL=de_core_news_md  # Instead of _lg

# Use faster embedding model
EMBEDDING_MODEL=paraphrase-multilingual-MiniLM-L12-v2

# Use GPU if available
CUDA_DEVICE=0

# Increase batch size
EMBEDDING_BATCH_SIZE=64
```

**Validation**:

```bash
# Benchmark different configurations
python tests/performance/benchmark.py
```

### 5. Caching

**Problem**: Repeated computations

**Solutions**:

```python
# Enable model caching (already implemented)
ENABLE_MODEL_CACHE=true
MODEL_CACHE_DIR=/mnt/fast-storage/models

# Add Redis for result caching (future)
REDIS_URL=redis://localhost:6379
ENABLE_RESULT_CACHE=true
CACHE_TTL=3600
```

### 6. Async Processing

**Problem**: Synchronous bottlenecks

**Solutions**:

```python
# Use async database queries
async def get_verification(id: str):
    async with database.session() as session:
        result = await session.execute(query)
        return result

# Async embeddings (future)
# Process sentences concurrently
```

### 7. Rate Limiting Tuning

**Problem**: Too many rate limit 429 errors

**Solutions**:

```bash
# Increase rate limits
RATE_LIMIT_PER_MINUTE=100  # From 60
RATE_LIMIT_BURST=20        # From 10

# Disable in development
ENABLE_RATE_LIMITING=false
```

---

## Troubleshooting

### High Latency (p95 > 1000ms)

**Symptoms**:
- Response times increasing
- p95/p99 much higher than p50
- Timeouts under load

**Diagnosis**:

```bash
# Check which benchmark is slow
python tests/performance/benchmark.py

# Profile under load
./tests/performance/scenarios.sh baseline

# Check logs
tail -f /var/log/auditor/app.log | grep "Verification completed"
```

**Common Causes & Fixes**:

1. **Database slow**:
   ```bash
   # Check connection pool exhaustion
   DB_POOL_SIZE=20
   DB_MAX_OVERFLOW=40
   ```

2. **Model inference slow**:
   ```bash
   # Use GPU
   CUDA_DEVICE=0

   # Use faster models
   SPACY_MODEL=de_core_news_md
   ```

3. **Too few workers**:
   ```bash
   # Increase workers
   WORKER_COUNT=8
   ```

4. **Disk I/O bottleneck**:
   ```bash
   # Use SSD
   # Cache models in memory
   MODEL_CACHE_DIR=/dev/shm/models
   ```

### Low Throughput (< 20 req/s at 50 concurrent)

**Symptoms**:
- RPS doesn't increase with concurrency
- CPU usage low despite load
- Many requests waiting

**Diagnosis**:

```bash
# Benchmark concurrency scaling
python tests/performance/benchmark.py

# Check worker processes
ps aux | grep uvicorn

# Check CPU usage
top
```

**Common Causes & Fixes**:

1. **Single-threaded execution**:
   ```bash
   # Increase workers
   WORKER_COUNT=8
   ```

2. **Database connection limit**:
   ```bash
   # Increase pool size
   DB_POOL_SIZE=20
   DB_MAX_OVERFLOW=40
   ```

3. **Lock contention**:
   ```python
   # Use thread-safe caching
   # Avoid global locks
   ```

4. **Network latency**:
   ```bash
   # Use connection pooling
   # Increase timeout
   REQUEST_TIMEOUT=60
   ```

### Memory Leaks

**Symptoms**:
- Memory grows continuously
- OOM kills after hours
- Memory doesn't stabilize

**Diagnosis**:

```bash
# Profile memory over time
python tests/performance/memory_profile.py --duration 1800 --plot

# Run soak test
./tests/performance/scenarios.sh soak

# Check growth rate
# If > 10 MB/min, likely leak
```

**Common Causes & Fixes**:

1. **Unclosed connections**:
   ```python
   # Always use context managers
   async with database.session() as session:
       ...
   ```

2. **Cached embeddings not evicted**:
   ```python
   # Add LRU cache eviction
   @lru_cache(maxsize=1000)
   def get_embedding(text: str):
       ...
   ```

3. **Large object retention**:
   ```python
   # Clear large objects
   del large_result
   gc.collect()
   ```

4. **Thread leaks**:
   ```bash
   # Check thread count
   ps -eLf | grep uvicorn | wc -l

   # Should be stable
   ```

### High Error Rate (> 5%)

**Symptoms**:
- Many 500 errors
- Timeouts
- Rate limit 429 errors

**Diagnosis**:

```bash
# Check error logs
tail -f /var/log/auditor/app.log | grep ERROR

# Load test to reproduce
./tests/performance/scenarios.sh stress

# Check error distribution in Locust report
```

**Common Causes & Fixes**:

1. **Timeouts**:
   ```bash
   # Increase timeout
   REQUEST_TIMEOUT=120
   ```

2. **Resource exhaustion**:
   ```bash
   # Scale resources
   # Increase DB connections
   # Add more workers
   ```

3. **Rate limiting**:
   ```bash
   # Adjust rate limits
   RATE_LIMIT_PER_MINUTE=200

   # Or disable in test
   ENABLE_RATE_LIMITING=false
   ```

4. **Model errors**:
   ```bash
   # Check model loading
   # Verify GPU availability
   # Check disk space for models
   ```

---

## Production Monitoring

### Prometheus Metrics

**Key Metrics to Monitor**:

```promql
# Request rate
rate(auditor_verify_requests_total[5m])

# Latency
histogram_quantile(0.95, auditor_verify_latency_seconds_bucket)

# Error rate
rate(auditor_verify_requests_total{status="error"}[5m])

# Memory usage
process_resident_memory_bytes

# CPU usage
rate(process_cpu_seconds_total[5m])
```

### Grafana Dashboards

**Create dashboard with**:

1. **Overview Panel**:
   - Request rate (5min average)
   - Error rate
   - Active users

2. **Latency Panel**:
   - p50, p95, p99 latencies
   - Heatmap of latency distribution

3. **System Panel**:
   - CPU usage
   - Memory usage
   - Database connections

4. **Errors Panel**:
   - Error rate by type
   - Recent error logs

### Alerting Rules

```yaml
# Alert on high error rate
- alert: HighErrorRate
  expr: rate(auditor_verify_requests_total{status="error"}[5m]) > 0.05
  for: 5m
  annotations:
    summary: "High error rate detected"

# Alert on high latency
- alert: HighLatency
  expr: histogram_quantile(0.95, auditor_verify_latency_seconds_bucket) > 2
  for: 5m
  annotations:
    summary: "p95 latency > 2s"

# Alert on memory leak
- alert: MemoryLeak
  expr: rate(process_resident_memory_bytes[1h]) > 10485760  # 10 MB/hour
  for: 3h
  annotations:
    summary: "Possible memory leak detected"
```

---

## Best Practices

### 1. Establish Baselines

- Run benchmarks on every release
- Track performance metrics over time
- Document expected performance
- Set up regression alerts

### 2. Test Early and Often

- Run smoke tests on every commit
- Run load tests weekly
- Run soak tests before major releases
- Automate in CI/CD

### 3. Test in Production-Like Environment

- Use same hardware specs
- Use same configuration
- Use realistic data volumes
- Enable all security features

### 4. Monitor During Tests

- Watch Prometheus metrics
- Check database connections
- Monitor memory usage
- Review logs in real-time

### 5. Gradual Load Increase

- Start with smoke test
- Increase load gradually
- Identify breaking point
- Plan capacity accordingly

### 6. Document Results

- Save test reports
- Track metrics over time
- Document optimizations
- Share findings with team

### 7. Optimize Iteratively

- Measure before optimizing
- Change one thing at a time
- Measure after change
- Validate improvement

---

## See Also

- [Performance Testing Tools](../tests/performance/README.md)
- [Deployment Guide](DEPLOYMENT.md)
- [Monitoring Guide](MONITORING.md)
- [Configuration Reference](CONFIGURATION.md)

---

**Built with ❤️ by the JuraGPT Team**
