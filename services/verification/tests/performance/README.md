# Performance Testing Suite

Comprehensive performance testing tools for the JuraGPT Auditor API.

## Quick Start

```bash
# Install dependencies
pip install locust psutil matplotlib

# Run quick smoke test
./tests/performance/scenarios.sh smoke

# Run benchmarks
python tests/performance/benchmark.py

# Run memory profiling
python tests/performance/memory_profile.py --duration 300 --plot
```

## Tools

### 1. Load Testing (Locust)

**File**: `locustfile.py`

Simulates realistic user load with different patterns:

- **AuditorUser**: Standard verification requests (70% of traffic)
- **BurstUser**: Rapid-fire requests (burst pattern)
- **HeavyUser**: Large requests with many sources

**Usage**:

```bash
# Interactive Web UI
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

### 2. Pre-configured Scenarios

**File**: `scenarios.sh`

Ready-to-run load testing scenarios:

| Scenario | Users | Duration | Purpose |
|----------|-------|----------|---------|
| `smoke` | 10 | 1 min | Quick smoke test |
| `baseline` | 50 | 5 min | Baseline performance |
| `stress` | 200 | 5 min | Stress test |
| `spike` | 500 | 2 min | Spike traffic |
| `burst` | 100 | 3 min | Burst pattern |
| `heavy` | 50 | 5 min | Heavy requests |
| `endurance` | 100 | 30 min | Sustained load |
| `soak` | 75 | 2 hours | Memory leak detection |

**Usage**:

```bash
# Run specific scenario
./tests/performance/scenarios.sh baseline

# Run against production
LOAD_TEST_HOST=https://api.example.com ./tests/performance/scenarios.sh stress

# Run all scenarios
./tests/performance/scenarios.sh all
```

### 3. Performance Benchmarks

**File**: `benchmark.py`

Measures baseline API performance:

- Single request latency
- Sequential throughput
- Concurrent request handling (10, 25, 50 threads)
- Different request sizes (1 source, all sources)
- Latency percentiles (p50, p95, p99)

**Usage**:

```bash
# Run benchmarks
python tests/performance/benchmark.py

# Custom target
python tests/performance/benchmark.py --url http://production:8888

# Save results
python tests/performance/benchmark.py --output results.json
```

**Output**:
- Console summary
- JSON results file
- Latency percentiles
- Throughput metrics

### 4. Memory Profiling

**File**: `memory_profile.py`

Monitors memory usage and detects leaks:

- RSS (Resident Set Size) memory
- Virtual memory size
- Memory growth over time
- Thread count
- File descriptor usage

**Usage**:

```bash
# Profile for 5 minutes
python tests/performance/memory_profile.py --duration 300

# Generate plot
python tests/performance/memory_profile.py --duration 300 --plot

# Custom sampling interval
python tests/performance/memory_profile.py --interval 10 --duration 600
```

**Output**:
- Console analysis
- JSON data file
- Memory usage plot (if matplotlib available)
- Memory leak warnings

## Typical Workflow

### 1. Baseline Performance

```bash
# Step 1: Run benchmarks to establish baseline
python tests/performance/benchmark.py

# Step 2: Run smoke test
./tests/performance/scenarios.sh smoke
```

### 2. Load Testing

```bash
# Step 1: Run baseline load test
./tests/performance/scenarios.sh baseline

# Step 2: Run stress test
./tests/performance/scenarios.sh stress

# Step 3: Run spike test
./tests/performance/scenarios.sh spike
```

### 3. Memory Profiling

```bash
# Step 1: Profile memory during load test
python tests/performance/memory_profile.py --duration 600 --plot &

# Step 2: Run load test in parallel
./tests/performance/scenarios.sh baseline

# Step 3: Check memory profile results
```

### 4. Production Testing

```bash
# Set production host
export LOAD_TEST_HOST=https://api.production.example.com

# Run conservative load test
./tests/performance/scenarios.sh baseline

# Monitor results
```

## Interpreting Results

### Locust Results

**Good Performance**:
- Response time p95 < 500ms
- Response time p99 < 1000ms
- Failure rate < 1%
- RPS > 50 (for 100 users)

**Warning Signs**:
- Response time p95 > 1000ms
- Response time p99 > 3000ms
- Failure rate > 5%
- Error rate increasing over time

### Benchmark Results

**Expected Performance**:
- Single request: 100-300ms
- Sequential throughput: 5-15 req/s
- Concurrent (10 threads): 20-40 req/s
- Concurrent (50 threads): 30-60 req/s

**Bottleneck Indicators**:
- High latency variance (p99/p50 > 5)
- Low throughput increase with concurrency
- Increasing failures at higher concurrency

### Memory Profile

**Healthy Pattern**:
- RSS memory growth < 5 MB/min
- Stable after warm-up period
- Thread count stable

**Memory Leak Indicators**:
- Continuous memory growth > 10 MB/min
- Memory not stabilizing
- Increasing thread/FD count

## Performance Targets

### Latency Targets

| Percentile | Target | Acceptable | Poor |
|------------|--------|------------|------|
| p50 | < 200ms | < 500ms | > 500ms |
| p95 | < 500ms | < 1000ms | > 1000ms |
| p99 | < 1000ms | < 2000ms | > 2000ms |

### Throughput Targets

| Concurrency | Target | Acceptable | Poor |
|-------------|--------|------------|------|
| 1 (sequential) | > 10 req/s | > 5 req/s | < 5 req/s |
| 10 (concurrent) | > 30 req/s | > 20 req/s | < 20 req/s |
| 50 (concurrent) | > 50 req/s | > 30 req/s | < 30 req/s |

### Memory Targets

| Metric | Target | Acceptable | Poor |
|--------|--------|------------|------|
| Initial RSS | < 500 MB | < 1 GB | > 1 GB |
| Growth rate | < 5 MB/min | < 10 MB/min | > 10 MB/min |
| Max RSS (1h) | < 1 GB | < 2 GB | > 2 GB |

## Troubleshooting

### High Latency

**Possible Causes**:
- Database connection pool exhausted
- Model inference bottleneck
- Insufficient workers
- Slow disk I/O

**Solutions**:
- Increase DB pool size
- Use GPU acceleration
- Increase worker count
- Use SSD storage

### Low Throughput

**Possible Causes**:
- Synchronous bottlenecks
- Single-threaded execution
- Database query slowness
- Network latency

**Solutions**:
- Enable async processing
- Increase worker count
- Optimize database queries
- Use connection pooling

### Memory Leaks

**Possible Causes**:
- Unclosed connections
- Cached embeddings not evicted
- Large object retention
- Thread leaks

**Solutions**:
- Implement connection cleanup
- Add LRU cache eviction
- Profile with memory_profiler
- Check for thread creation

### High Error Rate

**Possible Causes**:
- Timeouts under load
- Resource exhaustion
- Database connection errors
- Rate limiting triggered

**Solutions**:
- Increase timeouts
- Scale resources
- Increase connection limits
- Adjust rate limits

## Configuration

### Locust Configuration

Edit `locust.conf`:

```ini
# locust.conf
host = http://localhost:8888
users = 50
spawn-rate = 5
run-time = 5m
```

### Environment Variables

```bash
# Load test target
export LOAD_TEST_HOST=http://localhost:8888

# API authentication (if enabled)
export API_TOKEN=your-jwt-token
export API_KEY=your-api-key
```

## Reports

Performance test results are saved to:

```
tests/performance/reports/
├── baseline_20251030_123456.html       # Locust HTML report
├── baseline_20251030_123456_stats.csv  # Locust stats CSV
├── benchmark_results.json               # Benchmark results
└── memory_profile.json                  # Memory profile data
```

## Continuous Integration

Add to your CI pipeline:

```yaml
# .github/workflows/performance.yml
- name: Run Performance Tests
  run: |
    # Start API server
    docker-compose up -d auditor-api

    # Wait for health check
    sleep 10

    # Run benchmarks
    python tests/performance/benchmark.py

    # Run smoke test
    ./tests/performance/scenarios.sh smoke

    # Check for regressions
    python scripts/check_performance_regression.py
```

## See Also

- [Locust Documentation](https://docs.locust.io/)
- [Performance Testing Best Practices](../../docs/PERFORMANCE_TESTING.md)
- [Deployment Guide](../../docs/DEPLOYMENT.md)
