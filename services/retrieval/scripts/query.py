#!/usr/bin/env python3
"""
Query testing script for JuraGPT retrieval system.

Tests semantic search with sample legal queries.

Usage:
    python scripts/query.py [--query "Your query here"] [--top-k 5]
"""

import sys
import argparse
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.storage.qdrant_client import JuraGPTQdrantClient
from src.embedding.embedder import LegalTextEmbedder


def format_result(result: dict, index: int) -> str:
    """Format a single search result for display."""
    lines = [
        f"\n{'=' * 80}",
        f"Result {index}: {result.get('title', 'No Title')}",
        f"{'=' * 80}",
        f"Score: {result['score']:.4f}",
        f"Source: {result.get('source', 'Unknown')}",
        f"Type: {result['metadata'].get('type', 'unknown')}",
        f"URL: {result.get('url', 'N/A')}",
        f"\nText:\n{result['text'][:500]}{'...' if len(result['text']) > 500 else ''}",
    ]
    return "\n".join(lines)


def run_query(query: str, top_k: int = 5, filters: dict = None):
    """
    Run a single query and display results.

    Args:
        query: Search query text
        top_k: Number of results to return
        filters: Optional metadata filters
    """
    print(f"\n{'#' * 80}")
    print(f"Query: {query}")
    print(f"Top K: {top_k}")
    if filters:
        print(f"Filters: {json.dumps(filters)}")
    print(f"{'#' * 80}")

    # Initialize components
    print("\nInitializing components...")
    embedder = LegalTextEmbedder()
    qdrant_client = JuraGPTQdrantClient()

    # Get collection info
    info = qdrant_client.get_collection_info()
    print(f"Collection: {info['name']} ({info['points_count']} documents)")

    # Generate query embedding
    print("\nGenerating query embedding...")
    query_vector = embedder.encode_query(query)

    # Search
    print("Searching...")
    results = qdrant_client.search(
        query_vector=query_vector,
        top_k=top_k,
        filters=filters,
    )

    # Display results
    print(f"\n{'*' * 80}")
    print(f"Found {len(results)} results:")
    print(f"{'*' * 80}")

    for i, result in enumerate(results, 1):
        print(format_result(result, i))

    return results


def run_test_suite():
    """Run a suite of test queries."""
    test_queries = [
        {
            "query": "Wann haftet jemand nach §823 BGB?",
            "description": "Liability under tort law",
            "top_k": 3,
        },
        {
            "query": "Welche Voraussetzungen gelten für eine ordentliche Kündigung?",
            "description": "Employment termination requirements",
            "top_k": 3,
        },
        {
            "query": "Was ist das Grundrecht auf informationelle Selbstbestimmung?",
            "description": "Constitutional right to data privacy",
            "top_k": 3,
        },
        {
            "query": "Schadensersatz bei Vertragsverletzung",
            "description": "Damages for breach of contract",
            "top_k": 3,
        },
    ]

    print("\n" + "=" * 80)
    print("RUNNING TEST SUITE")
    print("=" * 80)

    all_results = []
    for i, test in enumerate(test_queries, 1):
        print(f"\n\nTest {i}/{len(test_queries)}: {test['description']}")
        results = run_query(test["query"], top_k=test["top_k"])
        all_results.append({"test": test, "results": results})

    # Summary
    print("\n\n" + "=" * 80)
    print("TEST SUITE SUMMARY")
    print("=" * 80)

    for i, item in enumerate(all_results, 1):
        test = item["test"]
        results = item["results"]
        avg_score = sum(r["score"] for r in results) / len(results) if results else 0

        print(f"\nTest {i}: {test['description']}")
        print(f"  Query: {test['query']}")
        print(f"  Results: {len(results)}")
        print(f"  Avg Score: {avg_score:.4f}")

        if results:
            top_result = results[0]
            print(f"  Top Result: {top_result.get('title', 'No title')} (score: {top_result['score']:.4f})")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="JuraGPT Query Testing")
    parser.add_argument(
        "--query",
        type=str,
        help="Custom query to search"
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Number of results to return (default: 5)"
    )
    parser.add_argument(
        "--filter-type",
        type=str,
        choices=["statute", "case", "regulation"],
        help="Filter by document type"
    )
    parser.add_argument(
        "--filter-law",
        type=str,
        help="Filter by law (e.g., BGB, StGB)"
    )
    parser.add_argument(
        "--test-suite",
        action="store_true",
        help="Run full test suite"
    )

    args = parser.parse_args()

    # Build filters
    filters = {}
    if args.filter_type:
        filters["type"] = args.filter_type
    if args.filter_law:
        filters["law"] = args.filter_law.upper()

    # Run query or test suite
    if args.test_suite:
        run_test_suite()
    elif args.query:
        run_query(args.query, top_k=args.top_k, filters=filters or None)
    else:
        # Default: run test suite
        run_test_suite()


if __name__ == "__main__":
    main()
