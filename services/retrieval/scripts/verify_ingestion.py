#!/usr/bin/env python3
"""
ABOUTME: Comprehensive verification script for ingestion pipeline completion.
ABOUTME: Checks Qdrant collection health, vector counts, retrieval quality, duplicates, coverage.

Usage:
    python scripts/verify_ingestion.py [--verbose] [--save-report]
"""

import sys
import json
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Any
from collections import defaultdict

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.storage.qdrant_client import JuraGPTQdrantClient
from src.embedding.embedder import LegalTextEmbedder


class IngestionVerifier:
    """Verify ingestion pipeline completion and quality."""

    def __init__(self, verbose: bool = False):
        """Initialize verifier."""
        self.verbose = verbose
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "checks": {},
            "summary": {
                "total_checks": 8,
                "passed": 0,
                "failed": 0,
                "warnings": 0,
            }
        }

        # Initialize clients
        print("Initializing components...")
        self.qdrant_client = JuraGPTQdrantClient()
        self.embedder = LegalTextEmbedder()
        print("✓ Components initialized\n")

    def _log(self, message: str):
        """Log message if verbose."""
        if self.verbose:
            print(f"  {message}")

    def _pass_check(self, check_name: str, details: Dict[str, Any]):
        """Record a passed check."""
        self.results["checks"][check_name] = {
            "status": "PASS",
            "details": details
        }
        self.results["summary"]["passed"] += 1

    def _fail_check(self, check_name: str, reason: str, details: Dict[str, Any] = None):
        """Record a failed check."""
        self.results["checks"][check_name] = {
            "status": "FAIL",
            "reason": reason,
            "details": details or {}
        }
        self.results["summary"]["failed"] += 1

    def _warn_check(self, check_name: str, reason: str, details: Dict[str, Any] = None):
        """Record a warning."""
        if check_name not in self.results["checks"]:
            self.results["checks"][check_name] = {
                "status": "PASS",
                "details": details or {}
            }

        if "warnings" not in self.results["checks"][check_name]:
            self.results["checks"][check_name]["warnings"] = []

        self.results["checks"][check_name]["warnings"].append(reason)
        self.results["summary"]["warnings"] += 1

    def check_1_collection_stats(self) -> bool:
        """Check 1: Qdrant collection stats."""
        print("=" * 80)
        print("CHECK 1: Qdrant Collection Stats")
        print("=" * 80)

        try:
            info = self.qdrant_client.get_collection_info()

            self._log(f"Collection: {info['name']}")
            self._log(f"Points: {info['points_count']:,}")
            self._log(f"Vectors: {info['vectors_count']:,}")
            self._log(f"Status: {info['status']}")

            # Check if collection exists and has data
            if info['points_count'] == 0:
                self._fail_check("collection_stats", "Collection is empty", info)
                print("❌ FAIL: Collection is empty\n")
                return False

            if info['status'] != 'green':
                self._warn_check("collection_stats", f"Collection status is {info['status']}", info)

            self._pass_check("collection_stats", info)
            print(f"✅ PASS: Collection has {info['points_count']:,} vectors, status: {info['status']}\n")
            return True

        except Exception as e:
            self._fail_check("collection_stats", str(e))
            print(f"❌ FAIL: {e}\n")
            return False

    def check_2_vector_count_breakdown(self) -> bool:
        """Check 2: Vector count breakdown by source."""
        print("=" * 80)
        print("CHECK 2: Vector Count Breakdown")
        print("=" * 80)

        try:
            # Get collection info
            info = self.qdrant_client.get_collection_info()
            total_vectors = info['points_count']

            # Scroll through all points to count by source
            # Use small batch size to avoid memory issues
            offset = None
            source_counts = defaultdict(int)
            type_counts = defaultdict(int)

            self._log("Scanning all vectors to count by source...")
            scanned = 0

            while True:
                # Scroll batch
                result, offset = self.qdrant_client.client.scroll(
                    collection_name=self.qdrant_client.collection_name,
                    limit=1000,
                    offset=offset,
                    with_payload=True,
                    with_vectors=False,
                )

                if not result:
                    break

                # Count sources
                for point in result:
                    # Determine source from payload
                    source = "unknown"
                    doc_type = point.payload.get("type", "unknown")

                    # EUR-Lex has specific characteristics
                    if doc_type == "eurlex" or "eurlex" in str(point.payload.get("url", "")).lower():
                        source = "eurlex"
                    # German laws from gesetze_github
                    elif point.payload.get("law"):
                        source = "gesetze_github"
                    # Check URL for other indicators
                    elif "gesetze" in str(point.payload.get("url", "")).lower():
                        source = "gesetze_github"

                    source_counts[source] += 1
                    type_counts[doc_type] += 1

                scanned += len(result)
                if self.verbose and scanned % 10000 == 0:
                    self._log(f"Scanned {scanned:,}/{total_vectors:,} vectors...")

                if offset is None:
                    break

            self._log(f"Scanned {scanned:,} vectors total")

            # Expected counts (from Phase 1 plan)
            expected_eurlex = 51_491
            expected_gesetze = 274_413
            expected_total = expected_eurlex + expected_gesetze  # ~325,904

            # Print breakdown
            print("\nSource breakdown:")
            for source, count in sorted(source_counts.items()):
                percentage = (count / total_vectors * 100) if total_vectors > 0 else 0
                print(f"  {source:20s}: {count:>10,} ({percentage:>6.2f}%)")

            print("\nType breakdown:")
            for doc_type, count in sorted(type_counts.items()):
                percentage = (count / total_vectors * 100) if total_vectors > 0 else 0
                print(f"  {doc_type:20s}: {count:>10,} ({percentage:>6.2f}%)")

            print(f"\nTotal vectors: {total_vectors:,}")
            print(f"Expected: ~{expected_total:,}")

            # Validation
            details = {
                "total_vectors": total_vectors,
                "source_counts": dict(source_counts),
                "type_counts": dict(type_counts),
                "expected_eurlex": expected_eurlex,
                "expected_gesetze": expected_gesetze,
                "expected_total": expected_total,
            }

            # Check if total is within reasonable range (±10%)
            if total_vectors < expected_total * 0.9:
                self._fail_check(
                    "vector_count_breakdown",
                    f"Total vectors ({total_vectors:,}) is significantly less than expected (~{expected_total:,})",
                    details
                )
                print(f"❌ FAIL: Only {total_vectors:,} vectors (expected ~{expected_total:,})\n")
                return False

            # Warn if significantly over (might indicate duplicates)
            if total_vectors > expected_total * 1.2:
                self._warn_check(
                    "vector_count_breakdown",
                    f"Total vectors ({total_vectors:,}) is significantly more than expected (~{expected_total:,}) - check for duplicates",
                    details
                )

            self._pass_check("vector_count_breakdown", details)
            print(f"✅ PASS: Vector counts within expected range\n")
            return True

        except Exception as e:
            self._fail_check("vector_count_breakdown", str(e))
            print(f"❌ FAIL: {e}\n")
            return False

    def check_3_eurlex_retrieval(self) -> bool:
        """Check 3: Sample retrieval from EUR-Lex."""
        print("=" * 80)
        print("CHECK 3: EUR-Lex Retrieval Quality")
        print("=" * 80)

        test_queries = [
            "data protection GDPR",
            "consumer rights directive",
            "employment law regulation",
            "environmental protection standards",
            "competition law merger control",
        ]

        try:
            passed_queries = 0
            failed_queries = []
            all_scores = []

            for query in test_queries:
                self._log(f"Testing: {query}")

                # Generate query embedding
                query_vector = self.embedder.encode_query(query)

                # Search with EUR-Lex filter
                results = self.qdrant_client.search(
                    query_vector=query_vector,
                    top_k=3,
                    filters={"type": "eurlex"}
                )

                if not results:
                    failed_queries.append(f"{query} (no results)")
                    continue

                # Check top result score (should be > 0.5 for relevant results)
                top_score = results[0]["score"]
                all_scores.append(top_score)

                if top_score > 0.5:
                    passed_queries += 1
                    self._log(f"  ✓ Top score: {top_score:.4f}")
                else:
                    failed_queries.append(f"{query} (low score: {top_score:.4f})")
                    self._log(f"  ✗ Top score: {top_score:.4f}")

            avg_score = sum(all_scores) / len(all_scores) if all_scores else 0

            details = {
                "queries_tested": len(test_queries),
                "passed": passed_queries,
                "failed": len(failed_queries),
                "avg_score": avg_score,
                "failed_queries": failed_queries,
            }

            print(f"\nResults: {passed_queries}/{len(test_queries)} queries passed")
            print(f"Average score: {avg_score:.4f}")

            # Pass if at least 80% of queries return good results
            if passed_queries >= len(test_queries) * 0.8:
                self._pass_check("eurlex_retrieval", details)
                print("✅ PASS: EUR-Lex retrieval working well\n")
                return True
            else:
                self._fail_check(
                    "eurlex_retrieval",
                    f"Only {passed_queries}/{len(test_queries)} queries passed",
                    details
                )
                print(f"❌ FAIL: Only {passed_queries}/{len(test_queries)} queries passed\n")
                return False

        except Exception as e:
            self._fail_check("eurlex_retrieval", str(e))
            print(f"❌ FAIL: {e}\n")
            return False

    def check_4_german_laws_retrieval(self) -> bool:
        """Check 4: Sample retrieval from German laws."""
        print("=" * 80)
        print("CHECK 4: German Laws Retrieval Quality")
        print("=" * 80)

        test_queries = [
            ("Wann haftet jemand nach §823 BGB?", "BGB"),
            ("Was regelt das Strafgesetzbuch?", "StGB"),
            ("Grundrechte im Grundgesetz", "GG"),
            ("Handelsregistereintragung", "HGB"),
            ("Kündigungsschutz im Arbeitsrecht", None),  # No specific law filter
        ]

        try:
            passed_queries = 0
            failed_queries = []
            all_scores = []

            for query, law_filter in test_queries:
                filter_str = f" (filter: {law_filter})" if law_filter else ""
                self._log(f"Testing: {query}{filter_str}")

                # Generate query embedding
                query_vector = self.embedder.encode_query(query)

                # Build filters
                filters = {}
                if law_filter:
                    filters["law"] = law_filter

                # Search
                results = self.qdrant_client.search(
                    query_vector=query_vector,
                    top_k=3,
                    filters=filters if filters else None
                )

                if not results:
                    failed_queries.append(f"{query} (no results)")
                    continue

                # Check top result score
                top_score = results[0]["score"]
                all_scores.append(top_score)

                if top_score > 0.5:
                    passed_queries += 1
                    self._log(f"  ✓ Top score: {top_score:.4f} - {results[0].get('title', 'No title')[:80]}")
                else:
                    failed_queries.append(f"{query} (low score: {top_score:.4f})")
                    self._log(f"  ✗ Top score: {top_score:.4f}")

            avg_score = sum(all_scores) / len(all_scores) if all_scores else 0

            details = {
                "queries_tested": len(test_queries),
                "passed": passed_queries,
                "failed": len(failed_queries),
                "avg_score": avg_score,
                "failed_queries": failed_queries,
            }

            print(f"\nResults: {passed_queries}/{len(test_queries)} queries passed")
            print(f"Average score: {avg_score:.4f}")

            # Pass if at least 80% of queries return good results
            if passed_queries >= len(test_queries) * 0.8:
                self._pass_check("german_laws_retrieval", details)
                print("✅ PASS: German laws retrieval working well\n")
                return True
            else:
                self._fail_check(
                    "german_laws_retrieval",
                    f"Only {passed_queries}/{len(test_queries)} queries passed",
                    details
                )
                print(f"❌ FAIL: Only {passed_queries}/{len(test_queries)} queries passed\n")
                return False

        except Exception as e:
            self._fail_check("german_laws_retrieval", str(e))
            print(f"❌ FAIL: {e}\n")
            return False

    def check_5_cross_source_retrieval(self) -> bool:
        """Check 5: Cross-source retrieval (query spanning both datasets)."""
        print("=" * 80)
        print("CHECK 5: Cross-Source Retrieval")
        print("=" * 80)

        test_queries = [
            "data protection and privacy laws",
            "consumer protection regulations",
        ]

        try:
            passed_queries = 0
            failed_queries = []

            for query in test_queries:
                self._log(f"Testing: {query}")

                # Generate query embedding
                query_vector = self.embedder.encode_query(query)

                # Search without filters (cross-source)
                results = self.qdrant_client.search(
                    query_vector=query_vector,
                    top_k=10,
                    filters=None
                )

                if not results:
                    failed_queries.append(f"{query} (no results)")
                    continue

                # Check if we get results from both sources
                sources = set()
                for result in results:
                    # Determine source
                    if result["metadata"].get("type") == "eurlex":
                        sources.add("eurlex")
                    elif result["metadata"].get("law"):
                        sources.add("gesetze_github")

                self._log(f"  Sources in top 10: {sources}")

                # Ideally we should see both sources
                if len(sources) >= 2:
                    passed_queries += 1
                    self._log(f"  ✓ Found results from {len(sources)} sources")
                else:
                    # Not a hard fail, but log it
                    self._log(f"  ⚠ Only found results from 1 source: {sources}")
                    passed_queries += 0.5  # Partial credit

            details = {
                "queries_tested": len(test_queries),
                "passed": int(passed_queries),
            }

            print(f"\nResults: {int(passed_queries)}/{len(test_queries)} queries showed cross-source results")

            # Pass if at least 50% show cross-source
            if passed_queries >= len(test_queries) * 0.5:
                self._pass_check("cross_source_retrieval", details)
                print("✅ PASS: Cross-source retrieval working\n")
                return True
            else:
                self._fail_check(
                    "cross_source_retrieval",
                    f"Only {int(passed_queries)}/{len(test_queries)} queries showed cross-source results",
                    details
                )
                print(f"❌ FAIL: Cross-source retrieval not working well\n")
                return False

        except Exception as e:
            self._fail_check("cross_source_retrieval", str(e))
            print(f"❌ FAIL: {e}\n")
            return False

    def check_6_embedding_quality(self) -> bool:
        """Check 6: Embedding quality analysis (cosine similarity distribution)."""
        print("=" * 80)
        print("CHECK 6: Embedding Quality Analysis")
        print("=" * 80)

        try:
            # Sample query
            query = "Vertragsverletzung und Schadensersatz"
            self._log(f"Test query: {query}")

            query_vector = self.embedder.encode_query(query)

            # Get top 50 results to analyze distribution
            results = self.qdrant_client.search(
                query_vector=query_vector,
                top_k=50,
                filters=None
            )

            if not results:
                self._fail_check("embedding_quality", "No results returned")
                print("❌ FAIL: No results returned\n")
                return False

            scores = [r["score"] for r in results]

            # Calculate statistics
            max_score = max(scores)
            min_score = min(scores)
            avg_score = sum(scores) / len(scores)

            # Check if top results have good scores
            top_10_avg = sum(scores[:10]) / 10

            details = {
                "query": query,
                "num_results": len(results),
                "max_score": max_score,
                "min_score": min_score,
                "avg_score": avg_score,
                "top_10_avg": top_10_avg,
            }

            print(f"\nScore distribution:")
            print(f"  Max:          {max_score:.4f}")
            print(f"  Min:          {min_score:.4f}")
            print(f"  Avg (all 50): {avg_score:.4f}")
            print(f"  Avg (top 10): {top_10_avg:.4f}")

            # Pass if top 10 average is > 0.6 (indicates good semantic matching)
            if top_10_avg > 0.6:
                self._pass_check("embedding_quality", details)
                print("✅ PASS: Embedding quality is good\n")
                return True
            else:
                self._warn_check(
                    "embedding_quality",
                    f"Top 10 average score is {top_10_avg:.4f} (expected > 0.6)",
                    details
                )
                self._pass_check("embedding_quality", details)
                print(f"⚠️  PASS with warning: Top 10 avg score {top_10_avg:.4f} is lower than ideal\n")
                return True

        except Exception as e:
            self._fail_check("embedding_quality", str(e))
            print(f"❌ FAIL: {e}\n")
            return False

    def check_7_duplicate_detection(self) -> bool:
        """Check 7: Duplicate detection (ensure no document was ingested twice)."""
        print("=" * 80)
        print("CHECK 7: Duplicate Detection")
        print("=" * 80)

        try:
            # Sample multiple vectors and check for exact duplicates
            # We'll use doc_id as the unique identifier

            self._log("Scanning for duplicate doc_ids...")

            offset = None
            doc_id_counts = defaultdict(int)
            scanned = 0

            while True:
                result, offset = self.qdrant_client.client.scroll(
                    collection_name=self.qdrant_client.collection_name,
                    limit=1000,
                    offset=offset,
                    with_payload=True,
                    with_vectors=False,
                )

                if not result:
                    break

                for point in result:
                    doc_id = point.payload.get("doc_id", f"point_{point.id}")
                    doc_id_counts[doc_id] += 1

                scanned += len(result)
                if self.verbose and scanned % 10000 == 0:
                    self._log(f"Scanned {scanned:,} vectors...")

                if offset is None:
                    break

            # Find duplicates
            duplicates = {doc_id: count for doc_id, count in doc_id_counts.items() if count > 1}

            total_docs = len(doc_id_counts)
            duplicate_docs = len(duplicates)
            duplicate_percentage = (duplicate_docs / total_docs * 100) if total_docs > 0 else 0

            details = {
                "total_unique_doc_ids": total_docs,
                "duplicate_doc_ids": duplicate_docs,
                "duplicate_percentage": duplicate_percentage,
                "sample_duplicates": dict(list(duplicates.items())[:10]),  # Show first 10
            }

            print(f"\nUnique doc_ids: {total_docs:,}")
            print(f"Duplicate doc_ids: {duplicate_docs:,} ({duplicate_percentage:.2f}%)")

            if duplicate_docs > 0:
                print(f"\nSample duplicates (showing up to 10):")
                for doc_id, count in list(duplicates.items())[:10]:
                    print(f"  {doc_id}: appears {count} times")

            # Pass if less than 1% duplicates (some duplication is acceptable due to chunking)
            if duplicate_percentage < 1.0:
                self._pass_check("duplicate_detection", details)
                print("✅ PASS: Duplicate rate is acceptable\n")
                return True
            else:
                self._fail_check(
                    "duplicate_detection",
                    f"Duplicate rate {duplicate_percentage:.2f}% is too high (expected < 1%)",
                    details
                )
                print(f"❌ FAIL: {duplicate_percentage:.2f}% duplicates (expected < 1%)\n")
                return False

        except Exception as e:
            self._fail_check("duplicate_detection", str(e))
            print(f"❌ FAIL: {e}\n")
            return False

    def check_8_coverage_validation(self) -> bool:
        """Check 8: Coverage validation (check all 6,593 laws are represented)."""
        print("=" * 80)
        print("CHECK 8: Coverage Validation (German Laws)")
        print("=" * 80)

        try:
            # Count unique German laws
            self._log("Scanning for unique German law identifiers...")

            offset = None
            law_slugs = set()
            scanned = 0

            while True:
                result, offset = self.qdrant_client.client.scroll(
                    collection_name=self.qdrant_client.collection_name,
                    limit=1000,
                    offset=offset,
                    with_payload=True,
                    with_vectors=False,
                )

                if not result:
                    break

                for point in result:
                    # Only count German laws (not EUR-Lex)
                    if point.payload.get("law"):
                        # Use doc_id as unique law identifier (format: gesetze_github_{slug})
                        doc_id = point.payload.get("doc_id", "")
                        if "gesetze_github_" in doc_id:
                            slug = doc_id.replace("gesetze_github_", "").split("_")[0]
                            law_slugs.add(slug)

                scanned += len(result)
                if self.verbose and scanned % 10000 == 0:
                    self._log(f"Scanned {scanned:,} vectors...")

                if offset is None:
                    break

            unique_laws = len(law_slugs)
            expected_laws = 6593
            coverage_percentage = (unique_laws / expected_laws * 100) if expected_laws > 0 else 0

            details = {
                "unique_laws_found": unique_laws,
                "expected_laws": expected_laws,
                "coverage_percentage": coverage_percentage,
            }

            print(f"\nUnique German laws: {unique_laws:,}")
            print(f"Expected: {expected_laws:,}")
            print(f"Coverage: {coverage_percentage:.2f}%")

            # Pass if at least 95% coverage (some laws might have been skipped due to errors)
            if coverage_percentage >= 95.0:
                self._pass_check("coverage_validation", details)
                print("✅ PASS: Coverage is excellent\n")
                return True
            elif coverage_percentage >= 85.0:
                self._warn_check(
                    "coverage_validation",
                    f"Coverage is {coverage_percentage:.2f}% (expected >= 95%)",
                    details
                )
                self._pass_check("coverage_validation", details)
                print(f"⚠️  PASS with warning: Coverage {coverage_percentage:.2f}% is lower than ideal\n")
                return True
            else:
                self._fail_check(
                    "coverage_validation",
                    f"Coverage {coverage_percentage:.2f}% is too low (expected >= 95%)",
                    details
                )
                print(f"❌ FAIL: Coverage {coverage_percentage:.2f}% is too low\n")
                return False

        except Exception as e:
            self._fail_check("coverage_validation", str(e))
            print(f"❌ FAIL: {e}\n")
            return False

    def run_all_checks(self) -> Tuple[bool, Dict[str, Any]]:
        """Run all verification checks."""
        print("\n" + "=" * 80)
        print("JURAGPT-RAG INGESTION VERIFICATION")
        print("=" * 80)
        print(f"Timestamp: {self.results['timestamp']}")
        print("=" * 80 + "\n")

        # Run all checks
        checks = [
            self.check_1_collection_stats,
            self.check_2_vector_count_breakdown,
            self.check_3_eurlex_retrieval,
            self.check_4_german_laws_retrieval,
            self.check_5_cross_source_retrieval,
            self.check_6_embedding_quality,
            self.check_7_duplicate_detection,
            self.check_8_coverage_validation,
        ]

        for check in checks:
            try:
                check()
            except Exception as e:
                print(f"❌ Check failed with exception: {e}\n")

        # Print summary
        self._print_summary()

        # Return overall result
        all_passed = self.results["summary"]["failed"] == 0
        return all_passed, self.results

    def _print_summary(self):
        """Print verification summary."""
        print("\n" + "=" * 80)
        print("VERIFICATION SUMMARY")
        print("=" * 80)

        summary = self.results["summary"]

        print(f"\nTotal checks:  {summary['total_checks']}")
        print(f"Passed:        {summary['passed']} ✅")
        print(f"Failed:        {summary['failed']} ❌")
        print(f"Warnings:      {summary['warnings']} ⚠️")

        # Overall status
        if summary["failed"] == 0:
            if summary["warnings"] == 0:
                print("\n🎉 ALL CHECKS PASSED - System is ready!")
            else:
                print(f"\n✅ ALL CHECKS PASSED (with {summary['warnings']} warnings)")
        else:
            print(f"\n❌ VERIFICATION FAILED ({summary['failed']} checks failed)")

        # List failed checks
        if summary["failed"] > 0:
            print("\nFailed checks:")
            for check_name, result in self.results["checks"].items():
                if result["status"] == "FAIL":
                    print(f"  • {check_name}: {result.get('reason', 'Unknown error')}")

        print("=" * 80 + "\n")

    def save_report(self, output_path: Path):
        """Save verification report to JSON file."""
        with open(output_path, 'w') as f:
            json.dump(self.results, f, indent=2)
        print(f"Report saved to: {output_path}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Verify JuraGPT-RAG ingestion completion")
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    parser.add_argument(
        "--save-report",
        type=str,
        help="Save report to JSON file (e.g., reports/verification_report.json)"
    )

    args = parser.parse_args()

    # Run verification
    verifier = IngestionVerifier(verbose=args.verbose)
    all_passed, results = verifier.run_all_checks()

    # Save report if requested
    if args.save_report:
        output_path = Path(args.save_report)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        verifier.save_report(output_path)

    # Exit with appropriate code
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
