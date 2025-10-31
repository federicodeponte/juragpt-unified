"""
ABOUTME: Performance benchmark suite for Auditor API
ABOUTME: Measures baseline performance metrics and identifies bottlenecks

This script runs comprehensive performance benchmarks:
- Single request latency
- Throughput (requests/second)
- Concurrent request handling
- Different request sizes
- Cache performance

Usage:
    python tests/performance/benchmark.py
    python tests/performance/benchmark.py --url http://production:8888
    python tests/performance/benchmark.py --output benchmark_results.json
"""

import argparse
import json
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Tuple

import requests


@dataclass
class BenchmarkResult:
    """Result of a single benchmark."""
    name: str
    description: str
    total_requests: int
    successful_requests: int
    failed_requests: int
    duration_seconds: float
    requests_per_second: float
    latency_p50_ms: float
    latency_p95_ms: float
    latency_p99_ms: float
    latency_min_ms: float
    latency_max_ms: float
    latency_avg_ms: float


class AuditorBenchmark:
    """
    Performance benchmark suite for Auditor API.

    Runs various benchmarks to measure API performance.
    """

    def __init__(self, api_url: str = "http://localhost:8888"):
        """
        Initialize benchmark suite.

        Args:
            api_url: Base URL of the API
        """
        self.api_url = api_url
        self.results: List[BenchmarkResult] = []

        # Test data
        self.test_answer = "Nach § 823 BGB haftet, wer vorsätzlich oder fahrlässig das Leben, den Körper, die Gesundheit, die Freiheit, das Eigentum oder ein sonstiges Recht eines anderen widerrechtlich verletzt."

        self.test_sources = [
            {
                "text": "Wer vorsätzlich oder fahrlässig das Leben, den Körper, die Gesundheit, die Freiheit, das Eigentum oder ein sonstiges Recht eines anderen widerrechtlich verletzt, ist dem anderen zum Ersatz des daraus entstehenden Schadens verpflichtet.",
                "source_id": "bgb_823_abs1",
                "score": 0.95,
                "metadata": {"law": "BGB", "section": "823"}
            },
            {
                "text": "Die gleiche Verpflichtung trifft denjenigen, welcher gegen ein den Schutz eines anderen bezweckendes Gesetz verstößt.",
                "source_id": "bgb_823_abs2",
                "score": 0.88,
                "metadata": {"law": "BGB", "section": "823"}
            },
            {
                "text": "Ergibt sich aus dem Inhalt des Gesetzes eine solche Schutzpflicht nicht, so ist der Schädiger dem Verletzten zum Ersatz verpflichtet.",
                "source_id": "bgb_823_abs3",
                "score": 0.82,
                "metadata": {"law": "BGB", "section": "823"}
            }
        ]

    def check_health(self) -> bool:
        """Check if API is healthy."""
        try:
            response = requests.get(f"{self.api_url}/health", timeout=5)
            return response.status_code == 200
        except Exception as e:
            print(f"❌ Health check failed: {e}")
            return False

    def single_request(self, num_sources: int = 3) -> Tuple[bool, float]:
        """
        Send a single verification request.

        Returns:
            (success, latency_ms)
        """
        request_data = {
            "answer": self.test_answer,
            "sources": self.test_sources[:num_sources]
        }

        start = time.perf_counter()
        try:
            response = requests.post(
                f"{self.api_url}/verify",
                json=request_data,
                timeout=30
            )
            latency = (time.perf_counter() - start) * 1000  # ms

            if response.status_code == 200:
                return (True, latency)
            else:
                return (False, latency)

        except Exception as e:
            latency = (time.perf_counter() - start) * 1000
            return (False, latency)

    def run_benchmark(
        self,
        name: str,
        description: str,
        num_requests: int,
        num_sources: int = 3,
        concurrent: int = 1
    ) -> BenchmarkResult:
        """
        Run a benchmark scenario.

        Args:
            name: Benchmark name
            description: Description
            num_requests: Total requests to send
            num_sources: Number of sources per request
            concurrent: Number of concurrent requests

        Returns:
            BenchmarkResult
        """
        print(f"\n🔬 {name}")
        print(f"   {description}")
        print(f"   Requests: {num_requests}, Concurrent: {concurrent}, Sources: {num_sources}")

        latencies: List[float] = []
        successes = 0
        failures = 0

        start_time = time.perf_counter()

        if concurrent == 1:
            # Sequential requests
            for i in range(num_requests):
                success, latency = self.single_request(num_sources)
                latencies.append(latency)
                if success:
                    successes += 1
                else:
                    failures += 1

                if (i + 1) % 10 == 0:
                    print(f"   Progress: {i + 1}/{num_requests} requests", end='\r')

        else:
            # Concurrent requests
            with ThreadPoolExecutor(max_workers=concurrent) as executor:
                futures = [
                    executor.submit(self.single_request, num_sources)
                    for _ in range(num_requests)
                ]

                completed = 0
                for future in as_completed(futures):
                    success, latency = future.result()
                    latencies.append(latency)
                    if success:
                        successes += 1
                    else:
                        failures += 1

                    completed += 1
                    if completed % 10 == 0:
                        print(f"   Progress: {completed}/{num_requests} requests", end='\r')

        duration = time.perf_counter() - start_time

        # Calculate statistics
        latencies.sort()
        result = BenchmarkResult(
            name=name,
            description=description,
            total_requests=num_requests,
            successful_requests=successes,
            failed_requests=failures,
            duration_seconds=duration,
            requests_per_second=num_requests / duration if duration > 0 else 0,
            latency_p50_ms=statistics.median(latencies),
            latency_p95_ms=latencies[int(len(latencies) * 0.95)] if latencies else 0,
            latency_p99_ms=latencies[int(len(latencies) * 0.99)] if latencies else 0,
            latency_min_ms=min(latencies) if latencies else 0,
            latency_max_ms=max(latencies) if latencies else 0,
            latency_avg_ms=statistics.mean(latencies) if latencies else 0,
        )

        print(f"\n   ✅ {successes}/{num_requests} successful ({successes/num_requests*100:.1f}%)")
        print(f"   ⚡ {result.requests_per_second:.2f} req/s")
        print(f"   ⏱️  Latency: p50={result.latency_p50_ms:.1f}ms, p95={result.latency_p95_ms:.1f}ms, p99={result.latency_p99_ms:.1f}ms")

        self.results.append(result)
        return result

    def run_all_benchmarks(self):
        """Run all benchmarks."""
        print("🚀 Auditor API Performance Benchmark Suite")
        print(f"   Target: {self.api_url}")
        print(f"   Time: {datetime.now().isoformat()}")

        # Check health
        if not self.check_health():
            print("\n❌ API is not healthy, cannot run benchmarks")
            return False

        print("\n✅ API is healthy")

        # Benchmark 1: Single request latency
        self.run_benchmark(
            name="Single Request Latency",
            description="Measure baseline single request performance",
            num_requests=50,
            num_sources=3,
            concurrent=1
        )

        # Benchmark 2: Sequential throughput
        self.run_benchmark(
            name="Sequential Throughput",
            description="Sequential requests to measure max processing speed",
            num_requests=100,
            num_sources=3,
            concurrent=1
        )

        # Benchmark 3: Low concurrency
        self.run_benchmark(
            name="Low Concurrency (10 threads)",
            description="Concurrent requests with 10 threads",
            num_requests=100,
            num_sources=3,
            concurrent=10
        )

        # Benchmark 4: Medium concurrency
        self.run_benchmark(
            name="Medium Concurrency (25 threads)",
            description="Concurrent requests with 25 threads",
            num_requests=100,
            num_sources=3,
            concurrent=25
        )

        # Benchmark 5: High concurrency
        self.run_benchmark(
            name="High Concurrency (50 threads)",
            description="Concurrent requests with 50 threads",
            num_requests=100,
            num_sources=3,
            concurrent=50
        )

        # Benchmark 6: Few sources (lightweight)
        self.run_benchmark(
            name="Few Sources (1 source)",
            description="Lightweight requests with minimal sources",
            num_requests=100,
            num_sources=1,
            concurrent=10
        )

        # Benchmark 7: Many sources (heavy)
        self.run_benchmark(
            name="Many Sources (all sources)",
            description="Heavy requests with all available sources",
            num_requests=50,
            num_sources=len(self.test_sources),
            concurrent=10
        )

        return True

    def print_summary(self):
        """Print benchmark summary."""
        if not self.results:
            print("❌ No benchmark results")
            return

        print("\n" + "="*80)
        print("📊 BENCHMARK SUMMARY")
        print("="*80)

        for result in self.results:
            print(f"\n{result.name}")
            print(f"  Success Rate: {result.successful_requests}/{result.total_requests} "
                  f"({result.successful_requests/result.total_requests*100:.1f}%)")
            print(f"  Throughput:   {result.requests_per_second:.2f} req/s")
            print(f"  Latency:")
            print(f"    Min:  {result.latency_min_ms:.1f}ms")
            print(f"    p50:  {result.latency_p50_ms:.1f}ms")
            print(f"    p95:  {result.latency_p95_ms:.1f}ms")
            print(f"    p99:  {result.latency_p99_ms:.1f}ms")
            print(f"    Max:  {result.latency_max_ms:.1f}ms")
            print(f"    Avg:  {result.latency_avg_ms:.1f}ms")

        print("\n" + "="*80)

        # Overall statistics
        total_requests = sum(r.total_requests for r in self.results)
        total_successful = sum(r.successful_requests for r in self.results)
        avg_throughput = statistics.mean([r.requests_per_second for r in self.results])
        avg_p50 = statistics.mean([r.latency_p50_ms for r in self.results])
        avg_p95 = statistics.mean([r.latency_p95_ms for r in self.results])

        print(f"\n🎯 Overall Statistics:")
        print(f"   Total Requests:       {total_requests}")
        print(f"   Total Successful:     {total_successful} ({total_successful/total_requests*100:.1f}%)")
        print(f"   Average Throughput:   {avg_throughput:.2f} req/s")
        print(f"   Average p50 Latency:  {avg_p50:.1f}ms")
        print(f"   Average p95 Latency:  {avg_p95:.1f}ms")

        print("\n" + "="*80)

    def save_results(self, filepath: str = "tests/performance/benchmark_results.json"):
        """Save benchmark results to JSON."""
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)

        data = {
            'metadata': {
                'api_url': self.api_url,
                'timestamp': datetime.now().isoformat(),
            },
            'results': [asdict(r) for r in self.results]
        }

        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)

        print(f"\n💾 Results saved to: {filepath}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Performance benchmark suite for Auditor API"
    )
    parser.add_argument(
        '--url',
        default='http://localhost:8888',
        help='API base URL (default: http://localhost:8888)'
    )
    parser.add_argument(
        '--output',
        default='tests/performance/benchmark_results.json',
        help='Output JSON file (default: tests/performance/benchmark_results.json)'
    )

    args = parser.parse_args()

    benchmark = AuditorBenchmark(api_url=args.url)

    # Run benchmarks
    success = benchmark.run_all_benchmarks()
    if not success:
        sys.exit(1)

    # Print summary
    benchmark.print_summary()

    # Save results
    benchmark.save_results(args.output)

    print("\n✅ Benchmarks completed successfully")
    sys.exit(0)


if __name__ == '__main__':
    main()
