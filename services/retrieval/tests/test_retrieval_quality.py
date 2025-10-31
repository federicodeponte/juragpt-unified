#!/usr/bin/env python3
"""
ABOUTME: Golden query test suite for RAG retrieval quality evaluation.
ABOUTME: Tests precision, recall, MRR, and latency across legal query categories.

Test Categories:
1. Specific legal references (§823 BGB, Art. 1 GG, etc.)
2. Conceptual legal queries (Schadensersatz, Kündigungsschutz, etc.)
3. Mixed German/EU law queries
4. Edge cases (ambiguous terms, rare laws, etc.)

Metrics:
- Precision@k: % of relevant results in top k
- Recall@k: % of total relevant docs found in top k
- MRR (Mean Reciprocal Rank): 1/rank of first relevant result
- Query latency: Time to retrieve results

Usage:
    python tests/test_retrieval_quality.py [--verbose] [--save-results]
"""

import sys
import json
import time
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Tuple, Any, Optional
from dataclasses import dataclass, asdict

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.storage.qdrant_client import JuraGPTQdrantClient
from src.embedding.embedder import LegalTextEmbedder


@dataclass
class QueryTest:
    """Test case for retrieval quality."""
    query: str
    category: str
    expected_relevant: List[str]  # List of keywords/patterns that should appear in results
    filters: Optional[Dict[str, str]] = None
    top_k: int = 10
    min_score: float = 0.5  # Minimum score for relevance
    description: str = ""


@dataclass
class QueryResult:
    """Result of a query test."""
    query: str
    category: str
    description: str

    # Results
    num_results: int
    top_score: float
    avg_score: float
    latency_ms: float

    # Metrics
    precision_at_5: float
    precision_at_10: float
    recall_at_5: float
    recall_at_10: float
    reciprocal_rank: float

    # Analysis
    relevant_found: List[str]
    relevant_missing: List[str]
    passed: bool
    failure_reason: Optional[str] = None


class RetrievalQualityTester:
    """Test suite for retrieval quality."""

    def __init__(self, verbose: bool = False):
        """Initialize tester."""
        self.verbose = verbose
        self.test_results: List[QueryResult] = []

        # Initialize clients
        print("Initializing components...")
        self.qdrant_client = JuraGPTQdrantClient()
        self.embedder = LegalTextEmbedder()
        print("✓ Components initialized\n")

        # Define test suite
        self.test_suite = self._build_test_suite()

    def _log(self, message: str):
        """Log message if verbose."""
        if self.verbose:
            print(f"  {message}")

    def _build_test_suite(self) -> List[QueryTest]:
        """Build comprehensive test suite."""
        tests = []

        # Category 1: Specific Legal References (BGB, StGB, GG, etc.)
        tests.extend([
            QueryTest(
                query="§823 BGB Haftung",
                category="specific_reference",
                expected_relevant=["823", "BGB", "Haftung", "Schadensersatz"],
                filters={"law": "BGB"},
                description="BGB §823 - Tort liability"
            ),
            QueryTest(
                query="Artikel 1 Grundgesetz Menschenwürde",
                category="specific_reference",
                expected_relevant=["Artikel 1", "GG", "Menschenwürde", "unantastbar"],
                filters={"law": "GG"},
                description="GG Art. 1 - Human dignity"
            ),
            QueryTest(
                query="§242 StGB Diebstahl",
                category="specific_reference",
                expected_relevant=["242", "StGB", "Diebstahl", "Wegnahme"],
                filters={"law": "StGB"},
                description="StGB §242 - Theft"
            ),
            QueryTest(
                query="§433 BGB Kaufvertrag",
                category="specific_reference",
                expected_relevant=["433", "BGB", "Kaufvertrag", "Verkäufer"],
                filters={"law": "BGB"},
                description="BGB §433 - Sales contract"
            ),
        ])

        # Category 2: Conceptual Legal Queries
        tests.extend([
            QueryTest(
                query="Schadensersatz bei Vertragsverletzung",
                category="conceptual",
                expected_relevant=["Schadensersatz", "Vertrag", "Pflichtverletzung"],
                description="Damages for breach of contract"
            ),
            QueryTest(
                query="Kündigungsschutz im Arbeitsrecht",
                category="conceptual",
                expected_relevant=["Kündigung", "Arbeit", "Schutz"],
                description="Employment termination protection"
            ),
            QueryTest(
                query="Erbrecht gesetzliche Erbfolge",
                category="conceptual",
                expected_relevant=["Erb", "gesetzlich", "Nachlass"],
                description="Statutory succession in inheritance law"
            ),
            QueryTest(
                query="Datenschutz informationelle Selbstbestimmung",
                category="conceptual",
                expected_relevant=["Daten", "Schutz", "informationell"],
                description="Data protection and privacy"
            ),
            QueryTest(
                query="Gewährleistung bei Kaufverträgen",
                category="conceptual",
                expected_relevant=["Gewährleistung", "Kauf", "Mangel"],
                description="Warranty in sales contracts"
            ),
        ])

        # Category 3: Mixed German/EU Law Queries
        tests.extend([
            QueryTest(
                query="GDPR Datenschutz Deutschland",
                category="mixed_eu_german",
                expected_relevant=["GDPR", "Datenschutz", "data protection"],
                description="GDPR and German data protection"
            ),
            QueryTest(
                query="consumer rights directive Verbraucherschutz",
                category="mixed_eu_german",
                expected_relevant=["consumer", "Verbraucher", "rights"],
                description="EU consumer rights and German consumer protection"
            ),
            QueryTest(
                query="employment law directive Arbeitsrecht",
                category="mixed_eu_german",
                expected_relevant=["employment", "Arbeit", "directive"],
                description="EU employment directives and German labor law"
            ),
        ])

        # Category 4: Edge Cases
        tests.extend([
            QueryTest(
                query="gute Sitten",
                category="edge_case",
                expected_relevant=["gute Sitten", "sittenwidrig", "138"],
                description="Ambiguous term - good morals (BGB §138)"
            ),
            QueryTest(
                query="Treu und Glauben",
                category="edge_case",
                expected_relevant=["Treu", "Glauben", "242"],
                description="General principle - good faith (BGB §242)"
            ),
            QueryTest(
                query="Schuldrecht Allgemeiner Teil",
                category="edge_case",
                expected_relevant=["Schuldrecht", "Allgemein", "BGB"],
                description="General section query - Law of Obligations"
            ),
        ])

        # Category 5: EUR-Lex Specific
        tests.extend([
            QueryTest(
                query="environmental protection directive",
                category="eurlex_specific",
                expected_relevant=["environment", "protection", "directive"],
                filters={"type": "eurlex"},
                description="Environmental protection in EU law"
            ),
            QueryTest(
                query="competition law merger regulation",
                category="eurlex_specific",
                expected_relevant=["competition", "merger", "regulation"],
                filters={"type": "eurlex"},
                description="EU merger control"
            ),
        ])

        return tests

    def _check_relevance(self, result: Dict[str, Any], expected_keywords: List[str]) -> bool:
        """Check if result is relevant based on expected keywords."""
        text = result.get("text", "").lower()
        title = result.get("title", "").lower()
        combined = text + " " + title

        # Check how many keywords appear
        matches = sum(1 for keyword in expected_keywords if keyword.lower() in combined)

        # Relevant if at least 50% of keywords match
        return matches >= len(expected_keywords) * 0.5

    def _calculate_metrics(
        self,
        results: List[Dict[str, Any]],
        expected_relevant: List[str],
        min_score: float
    ) -> Dict[str, float]:
        """Calculate precision, recall, and MRR."""

        # Identify which results are relevant
        relevant_results = []
        for i, result in enumerate(results):
            score = result.get("score", 0)
            if score >= min_score and self._check_relevance(result, expected_relevant):
                relevant_results.append(i)

        # Precision@k
        precision_at_5 = len([i for i in relevant_results if i < 5]) / min(5, len(results)) if results else 0
        precision_at_10 = len([i for i in relevant_results if i < 10]) / min(10, len(results)) if results else 0

        # Recall@k (assume we want to find at least 3 relevant docs)
        expected_num_relevant = 3
        recall_at_5 = len([i for i in relevant_results if i < 5]) / expected_num_relevant
        recall_at_10 = len([i for i in relevant_results if i < 10]) / expected_num_relevant

        # MRR (Mean Reciprocal Rank) - rank of first relevant result
        reciprocal_rank = 0
        if relevant_results:
            first_relevant_rank = min(relevant_results) + 1  # 1-indexed
            reciprocal_rank = 1.0 / first_relevant_rank

        return {
            "precision_at_5": precision_at_5,
            "precision_at_10": precision_at_10,
            "recall_at_5": recall_at_5,
            "recall_at_10": recall_at_10,
            "reciprocal_rank": reciprocal_rank,
        }

    def run_test(self, test: QueryTest) -> QueryResult:
        """Run a single test query."""
        self._log(f"Testing: {test.query}")

        # Measure latency
        start_time = time.time()

        # Generate query embedding
        query_vector = self.embedder.encode_query(test.query)

        # Search
        results = self.qdrant_client.search(
            query_vector=query_vector,
            top_k=test.top_k,
            filters=test.filters,
        )

        latency_ms = (time.time() - start_time) * 1000

        # Calculate metrics
        metrics = self._calculate_metrics(results, test.expected_relevant, test.min_score)

        # Analyze results
        num_results = len(results)
        top_score = results[0]["score"] if results else 0
        avg_score = sum(r["score"] for r in results) / len(results) if results else 0

        # Check which expected keywords were found
        relevant_found = []
        for keyword in test.expected_relevant:
            for result in results[:5]:  # Check top 5
                text = result.get("text", "").lower()
                title = result.get("title", "").lower()
                if keyword.lower() in text or keyword.lower() in title:
                    relevant_found.append(keyword)
                    break

        relevant_missing = [k for k in test.expected_relevant if k not in relevant_found]

        # Determine pass/fail
        passed = True
        failure_reason = None

        if num_results == 0:
            passed = False
            failure_reason = "No results returned"
        elif top_score < test.min_score:
            passed = False
            failure_reason = f"Top score {top_score:.4f} < threshold {test.min_score}"
        elif metrics["precision_at_5"] < 0.4:  # At least 40% precision
            passed = False
            failure_reason = f"Precision@5 {metrics['precision_at_5']:.2f} too low"
        elif metrics["reciprocal_rank"] < 0.2:  # First relevant result in top 5
            passed = False
            failure_reason = f"MRR {metrics['reciprocal_rank']:.2f} too low"

        # Create result
        result = QueryResult(
            query=test.query,
            category=test.category,
            description=test.description,
            num_results=num_results,
            top_score=top_score,
            avg_score=avg_score,
            latency_ms=latency_ms,
            precision_at_5=metrics["precision_at_5"],
            precision_at_10=metrics["precision_at_10"],
            recall_at_5=metrics["recall_at_5"],
            recall_at_10=metrics["recall_at_10"],
            reciprocal_rank=metrics["reciprocal_rank"],
            relevant_found=relevant_found,
            relevant_missing=relevant_missing,
            passed=passed,
            failure_reason=failure_reason,
        )

        # Log result
        status = "✅ PASS" if passed else f"❌ FAIL: {failure_reason}"
        self._log(f"  {status}")
        self._log(f"  Score: {top_score:.4f}, P@5: {metrics['precision_at_5']:.2f}, MRR: {metrics['reciprocal_rank']:.2f}, Latency: {latency_ms:.0f}ms")

        return result

    def run_all_tests(self) -> Tuple[List[QueryResult], Dict[str, Any]]:
        """Run all tests and return results with summary."""
        print("=" * 80)
        print("RETRIEVAL QUALITY TEST SUITE")
        print("=" * 80)
        print(f"Total tests: {len(self.test_suite)}\n")

        results = []

        for i, test in enumerate(self.test_suite, 1):
            print(f"\nTest {i}/{len(self.test_suite)}: {test.description}")
            print(f"Category: {test.category}")
            print(f"Query: {test.query}")

            try:
                result = self.run_test(test)
                results.append(result)

                # Print summary
                status = "✅ PASS" if result.passed else f"❌ FAIL: {result.failure_reason}"
                print(f"  {status}")
                print(f"  Top score: {result.top_score:.4f}, P@5: {result.precision_at_5:.2f}, MRR: {result.reciprocal_rank:.2f}")
                print(f"  Latency: {result.latency_ms:.0f}ms")

            except Exception as e:
                print(f"❌ ERROR: {e}")
                # Create failed result
                result = QueryResult(
                    query=test.query,
                    category=test.category,
                    description=test.description,
                    num_results=0,
                    top_score=0,
                    avg_score=0,
                    latency_ms=0,
                    precision_at_5=0,
                    precision_at_10=0,
                    recall_at_5=0,
                    recall_at_10=0,
                    reciprocal_rank=0,
                    relevant_found=[],
                    relevant_missing=test.expected_relevant,
                    passed=False,
                    failure_reason=str(e),
                )
                results.append(result)

        # Calculate summary statistics
        summary = self._calculate_summary(results)

        # Print summary
        self._print_summary(summary)

        return results, summary

    def _calculate_summary(self, results: List[QueryResult]) -> Dict[str, Any]:
        """Calculate summary statistics."""
        total_tests = len(results)
        passed_tests = sum(1 for r in results if r.passed)
        failed_tests = total_tests - passed_tests

        # By category
        category_stats = {}
        for result in results:
            cat = result.category
            if cat not in category_stats:
                category_stats[cat] = {"total": 0, "passed": 0}
            category_stats[cat]["total"] += 1
            if result.passed:
                category_stats[cat]["passed"] += 1

        # Average metrics
        avg_precision_at_5 = sum(r.precision_at_5 for r in results) / total_tests
        avg_precision_at_10 = sum(r.precision_at_10 for r in results) / total_tests
        avg_recall_at_5 = sum(r.recall_at_5 for r in results) / total_tests
        avg_recall_at_10 = sum(r.recall_at_10 for r in results) / total_tests
        avg_mrr = sum(r.reciprocal_rank for r in results) / total_tests
        avg_latency = sum(r.latency_ms for r in results) / total_tests
        avg_top_score = sum(r.top_score for r in results) / total_tests

        return {
            "timestamp": datetime.now().isoformat(),
            "total_tests": total_tests,
            "passed": passed_tests,
            "failed": failed_tests,
            "pass_rate": passed_tests / total_tests if total_tests > 0 else 0,
            "category_stats": category_stats,
            "avg_metrics": {
                "precision_at_5": avg_precision_at_5,
                "precision_at_10": avg_precision_at_10,
                "recall_at_5": avg_recall_at_5,
                "recall_at_10": avg_recall_at_10,
                "mrr": avg_mrr,
                "latency_ms": avg_latency,
                "top_score": avg_top_score,
            }
        }

    def _print_summary(self, summary: Dict[str, Any]):
        """Print test summary."""
        print("\n" + "=" * 80)
        print("TEST SUMMARY")
        print("=" * 80)

        print(f"\nOverall Results:")
        print(f"  Total tests: {summary['total_tests']}")
        print(f"  Passed: {summary['passed']} ✅")
        print(f"  Failed: {summary['failed']} ❌")
        print(f"  Pass rate: {summary['pass_rate']:.1%}")

        print(f"\nResults by Category:")
        for category, stats in summary['category_stats'].items():
            pass_rate = stats['passed'] / stats['total'] if stats['total'] > 0 else 0
            print(f"  {category:25s}: {stats['passed']}/{stats['total']} ({pass_rate:.1%})")

        print(f"\nAverage Metrics:")
        metrics = summary['avg_metrics']
        print(f"  Precision@5:  {metrics['precision_at_5']:.3f}")
        print(f"  Precision@10: {metrics['precision_at_10']:.3f}")
        print(f"  Recall@5:     {metrics['recall_at_5']:.3f}")
        print(f"  Recall@10:    {metrics['recall_at_10']:.3f}")
        print(f"  MRR:          {metrics['mrr']:.3f}")
        print(f"  Top Score:    {metrics['top_score']:.3f}")
        print(f"  Latency:      {metrics['latency_ms']:.0f}ms")

        # Overall assessment
        if summary['pass_rate'] >= 0.9:
            print("\n🎉 EXCELLENT: Retrieval quality is very good!")
        elif summary['pass_rate'] >= 0.75:
            print("\n✅ GOOD: Retrieval quality is acceptable, minor tuning needed")
        elif summary['pass_rate'] >= 0.5:
            print("\n⚠️  NEEDS IMPROVEMENT: Retrieval quality has issues")
        else:
            print("\n❌ POOR: Retrieval quality needs significant improvement")

        print("=" * 80 + "\n")

    def save_results(self, output_path: Path):
        """Save test results to JSON file."""
        output_data = {
            "test_results": [asdict(r) for r in self.test_results],
            "summary": self._calculate_summary(self.test_results),
        }

        with open(output_path, 'w') as f:
            json.dump(output_data, f, indent=2)

        print(f"Results saved to: {output_path}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="JuraGPT-RAG Retrieval Quality Test Suite")
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    parser.add_argument(
        "--save-results",
        type=str,
        help="Save results to JSON file (e.g., results/retrieval_quality.json)"
    )
    parser.add_argument(
        "--category",
        type=str,
        help="Run tests for specific category only"
    )

    args = parser.parse_args()

    # Run tests
    tester = RetrievalQualityTester(verbose=args.verbose)

    # Filter by category if specified
    if args.category:
        tester.test_suite = [t for t in tester.test_suite if t.category == args.category]
        print(f"Running {len(tester.test_suite)} tests for category: {args.category}\n")

    results, summary = tester.run_all_tests()
    tester.test_results = results

    # Save results if requested
    if args.save_results:
        output_path = Path(args.save_results)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        tester.save_results(output_path)

    # Exit with appropriate code
    sys.exit(0 if summary['pass_rate'] >= 0.75 else 1)


if __name__ == "__main__":
    main()
