"""
ABOUTME: Locust load testing suite for JuraGPT Auditor API
ABOUTME: Simulates realistic verification workloads with various request patterns

This file defines load testing scenarios using Locust to measure:
- Request throughput (requests/second)
- Response latency (p50, p95, p99)
- Error rates
- System behavior under load

Usage:
    locust -f tests/performance/locustfile.py --host http://localhost:8888
    locust -f tests/performance/locustfile.py --host http://localhost:8888 --headless -u 100 -r 10 -t 5m
"""

import json
import random
from typing import List, Dict, Any

from locust import HttpUser, task, between, events
from locust.runners import MasterRunner


# Sample test data
SAMPLE_ANSWERS = [
    "Nach § 823 BGB haftet, wer vorsätzlich oder fahrlässig das Leben, den Körper, die Gesundheit, die Freiheit, das Eigentum oder ein sonstiges Recht eines anderen widerrechtlich verletzt.",
    "Die Verjährungsfrist beträgt nach § 195 BGB drei Jahre.",
    "Nach Art. 1 GG ist die Würde des Menschen unantastbar.",
    "Der Kaufvertrag nach § 433 BGB verpflichtet den Verkäufer zur Übergabe der Sache und zur Verschaffung des Eigentums.",
    "Nach § 312 BGB kann bei Verträgen im elektronischen Geschäftsverkehr ein Widerrufsrecht bestehen.",
]

SAMPLE_SOURCES = [
    {
        "text": "Wer vorsätzlich oder fahrlässig das Leben, den Körper, die Gesundheit, die Freiheit, das Eigentum oder ein sonstiges Recht eines anderen widerrechtlich verletzt, ist dem anderen zum Ersatz des daraus entstehenden Schadens verpflichtet.",
        "source_id": "bgb_823_abs1",
        "score": 0.95,
        "metadata": {"law": "BGB", "section": "823", "paragraph": "1"}
    },
    {
        "text": "Die regelmäßige Verjährungsfrist beträgt drei Jahre.",
        "source_id": "bgb_195",
        "score": 0.92,
        "metadata": {"law": "BGB", "section": "195"}
    },
    {
        "text": "Die Würde des Menschen ist unantastbar. Sie zu achten und zu schützen ist Verpflichtung aller staatlichen Gewalt.",
        "source_id": "gg_art1_abs1",
        "score": 0.98,
        "metadata": {"law": "GG", "article": "1", "paragraph": "1"}
    },
    {
        "text": "Durch den Kaufvertrag wird der Verkäufer einer Sache verpflichtet, dem Käufer die Sache zu übergeben und das Eigentum an der Sache zu verschaffen.",
        "source_id": "bgb_433_abs1",
        "score": 0.94,
        "metadata": {"law": "BGB", "section": "433", "paragraph": "1"}
    },
]


def generate_verification_request(
    num_sources: int = 3,
    threshold: float = 0.75,
    strict_mode: bool = False
) -> Dict[str, Any]:
    """Generate a realistic verification request."""
    return {
        "answer": random.choice(SAMPLE_ANSWERS),
        "sources": random.sample(SAMPLE_SOURCES, min(num_sources, len(SAMPLE_SOURCES))),
        "threshold": threshold,
        "strict_mode": strict_mode,
        "config": {
            "language": "de",
            "domain": "legal",
            "enable_citations": True,
            "enable_retry": True
        }
    }


class AuditorUser(HttpUser):
    """
    Base user class for Auditor API load testing.

    Simulates a typical user making verification requests with varying patterns.
    """

    # Wait 1-3 seconds between requests (simulates realistic user behavior)
    wait_time = between(1, 3)

    def on_start(self):
        """Called when a user starts. Can be used for authentication."""
        # Health check to warm up
        self.client.get("/health")

    @task(10)
    def verify_standard(self):
        """Standard verification request (most common pattern)."""
        request = generate_verification_request(num_sources=3, threshold=0.75)

        with self.client.post(
            "/verify",
            json=request,
            catch_response=True,
            name="/verify (standard)"
        ) as response:
            if response.status_code == 200:
                data = response.json()
                # Validate response structure
                if "overall_confidence" in data and "sentence_results" in data:
                    response.success()
                else:
                    response.failure(f"Invalid response structure: {data.keys()}")
            else:
                response.failure(f"HTTP {response.status_code}: {response.text}")

    @task(3)
    def verify_many_sources(self):
        """Verification with many sources (heavier load)."""
        request = generate_verification_request(num_sources=4, threshold=0.75)

        with self.client.post(
            "/verify",
            json=request,
            catch_response=True,
            name="/verify (many sources)"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"HTTP {response.status_code}")

    @task(2)
    def verify_strict_mode(self):
        """Verification in strict mode (higher threshold)."""
        request = generate_verification_request(num_sources=3, threshold=0.85, strict_mode=True)

        with self.client.post(
            "/verify",
            json=request,
            catch_response=True,
            name="/verify (strict mode)"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"HTTP {response.status_code}")

    @task(1)
    def health_check(self):
        """Health check endpoint (lightweight monitoring)."""
        with self.client.get("/health", name="/health", catch_response=True) as response:
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "healthy":
                    response.success()
                else:
                    response.failure(f"Unhealthy: {data}")
            else:
                response.failure(f"HTTP {response.status_code}")

    @task(1)
    def get_metrics(self):
        """Prometheus metrics endpoint."""
        with self.client.get("/metrics", name="/metrics", catch_response=True) as response:
            if response.status_code in [200, 404]:  # 404 if metrics disabled
                response.success()
            else:
                response.failure(f"HTTP {response.status_code}")


class BurstUser(HttpUser):
    """
    Burst user pattern - rapid requests with short pauses.

    Simulates burst traffic patterns (e.g., automated systems).
    """

    # Very short wait time (burst pattern)
    wait_time = between(0.1, 0.5)

    @task
    def verify_burst(self):
        """Rapid verification requests."""
        request = generate_verification_request(num_sources=2, threshold=0.75)

        with self.client.post(
            "/verify",
            json=request,
            catch_response=True,
            name="/verify (burst)"
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 429:  # Rate limited
                response.success()  # Expected behavior
            else:
                response.failure(f"HTTP {response.status_code}")


class HeavyUser(HttpUser):
    """
    Heavy user pattern - large requests.

    Simulates users with large verification requests.
    """

    wait_time = between(2, 5)

    @task
    def verify_large(self):
        """Large verification requests (all sources)."""
        request = generate_verification_request(num_sources=len(SAMPLE_SOURCES), threshold=0.75)

        with self.client.post(
            "/verify",
            json=request,
            catch_response=True,
            name="/verify (large)"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"HTTP {response.status_code}")


# Event hooks for custom metrics
@events.init.add_listener
def on_locust_init(environment, **kwargs):
    """Initialize custom metrics on Locust startup."""
    if isinstance(environment.runner, MasterRunner):
        print("Running in master mode")
    else:
        print(f"Load test starting against: {environment.host}")


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Hook for test start."""
    print("🚀 Load test starting...")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Hook for test stop - print summary."""
    print("✅ Load test completed")

    stats = environment.stats.total
    print(f"\n📊 Summary:")
    print(f"   Total Requests: {stats.num_requests}")
    print(f"   Failures: {stats.num_failures} ({stats.fail_ratio * 100:.2f}%)")
    print(f"   Median Response Time: {stats.median_response_time}ms")
    print(f"   95th Percentile: {stats.get_response_time_percentile(0.95)}ms")
    print(f"   99th Percentile: {stats.get_response_time_percentile(0.99)}ms")
    print(f"   RPS: {stats.total_rps:.2f}")
    print(f"   Avg Response Time: {stats.avg_response_time:.2f}ms")
