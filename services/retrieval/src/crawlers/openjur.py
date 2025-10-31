"""
ABOUTME: Crawler for German court decisions from OpenJur API.
ABOUTME: Fetches case headnotes, full text, and metadata for legal RAG corpus.
"""

import os
import json
import logging
import time
from typing import List, Dict, Any, Optional
from pathlib import Path
import requests
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OpenJurCrawler:
    """Crawler for OpenJur court decisions API."""

    def __init__(self, base_url: Optional[str] = None, output_dir: Optional[str] = None):
        """
        Initialize OpenJur crawler.

        Args:
            base_url: Base URL for OpenJur API (defaults to env)
            output_dir: Directory to save raw data (defaults to data/raw/)
        """
        self.base_url = base_url or os.getenv("OPENJUR_API_BASE_URL", "https://openjur.de/api")
        self.output_dir = Path(output_dir or "data/raw")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Important German courts
        self.courts = {
            "BVerfG": "Bundesverfassungsgericht",
            "BGH": "Bundesgerichtshof",
            "BVerwG": "Bundesverwaltungsgericht",
            "BFH": "Bundesfinanzhof",
            "BAG": "Bundesarbeitsgericht",
            "BSG": "Bundessozialgericht",
        }

        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "JuraGPT-Research/1.0 (Educational/Research Purpose)",
                "Accept": "application/json",
            }
        )

    def search_cases(
        self,
        court: Optional[str] = None,
        query: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Search for court cases via OpenJur API.

        Args:
            court: Court filter (e.g., "BGH", "BVerfG")
            query: Search query string
            limit: Number of results per page
            offset: Pagination offset

        Returns:
            List of case documents
        """
        # Note: Actual OpenJur API endpoint structure may vary
        # This is a generic implementation that may need adjustment
        search_url = f"{self.base_url}/search"

        params = {"limit": limit, "offset": offset}

        if court:
            params["gericht"] = court
        if query:
            params["q"] = query

        try:
            response = self.session.get(search_url, params=params, timeout=30)
            response.raise_for_status()

            # Try to parse JSON response
            data = response.json()

            # Extract cases (API structure may vary)
            if isinstance(data, dict) and "results" in data:
                cases = data["results"]
            elif isinstance(data, list):
                cases = data
            else:
                logger.warning(f"Unexpected API response format: {type(data)}")
                return []

            logger.info(f"Found {len(cases)} cases for court={court}, query={query}")
            return cases

        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {e}")
            return []
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            return []

    def get_case_details(self, case_id: str) -> Optional[Dict[str, Any]]:
        """
        Get full details for a specific case.

        Args:
            case_id: Case identifier

        Returns:
            Case document with full text
        """
        detail_url = f"{self.base_url}/cases/{case_id}"

        try:
            response = self.session.get(detail_url, timeout=30)
            response.raise_for_status()
            return response.json()

        except Exception as e:
            logger.error(f"Error fetching case {case_id}: {e}")
            return None

    def crawl_court_cases(
        self, court: str, max_cases: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Crawl recent cases from a specific court.

        Args:
            court: Court abbreviation (e.g., "BGH")
            max_cases: Maximum number of cases to crawl

        Returns:
            List of processed case documents
        """
        logger.info(f"Crawling cases from {court} ({self.courts.get(court, 'Unknown')})...")

        documents = []
        offset = 0
        page_size = 10

        while len(documents) < max_cases:
            # Fetch page of results
            cases = self.search_cases(court=court, limit=page_size, offset=offset)

            if not cases:
                break

            # Process each case
            for case in cases:
                if len(documents) >= max_cases:
                    break

                doc = self._process_case(case, court)
                if doc:
                    documents.append(doc)

            offset += page_size
            time.sleep(1)  # Rate limiting

        logger.info(f"Crawled {len(documents)} cases from {court}")
        return documents

    def _process_case(self, case_data: Dict[str, Any], court: str) -> Optional[Dict[str, Any]]:
        """
        Process raw case data into standardized document format.

        Args:
            case_data: Raw case data from API
            court: Court abbreviation

        Returns:
            Processed document dictionary
        """
        try:
            # Extract fields (field names may vary depending on actual API)
            case_id = case_data.get("aktenzeichen") or case_data.get("id")
            title = case_data.get("title") or case_data.get("leitsatz", "")

            # Combine headnote (Leitsatz) and full text if available
            leitsatz = case_data.get("leitsatz", "")
            full_text = case_data.get("text") or case_data.get("volltext", "")

            # Use headnote for title if no separate title
            if not title and leitsatz:
                title = leitsatz[:200] + "..." if len(leitsatz) > 200 else leitsatz

            # Combine leitsatz and full text
            text_parts = []
            if leitsatz:
                text_parts.append(f"Leitsatz: {leitsatz}")
            if full_text:
                text_parts.append(f"\n\n{full_text}")

            text = "\n\n".join(text_parts) if text_parts else ""

            if not text or len(text) < 50:
                logger.warning(f"Case {case_id} has insufficient text")
                return None

            # Extract metadata
            date = case_data.get("datum") or case_data.get("date", "")
            url = case_data.get("url") or f"https://openjur.de/u/{case_id}"

            # Create document
            doc = {
                "doc_id": f"{court}-{case_id}".replace("/", "-").replace(" ", "-"),
                "title": title,
                "text": text,
                "url": url,
                "type": "case",
                "jurisdiction": "DE",
                "court": court,
                "case_id": case_id,
                "date": date,
                "court_name": self.courts.get(court, court),
            }

            return doc

        except Exception as e:
            logger.error(f"Error processing case: {e}")
            return None

    def crawl_all_courts(self, max_cases_per_court: int = 10) -> List[Dict[str, Any]]:
        """
        Crawl cases from all major courts.

        Args:
            max_cases_per_court: Max cases per court

        Returns:
            List of all case documents
        """
        all_documents = []

        for court in self.courts.keys():
            docs = self.crawl_court_cases(court, max_cases=max_cases_per_court)
            all_documents.extend(docs)
            time.sleep(2)  # Rate limiting between courts

        logger.info(f"Total cases crawled: {len(all_documents)}")
        return all_documents

    def save_documents(self, documents: List[Dict[str, Any]], filename: str = "cases.jsonl"):
        """
        Save documents to JSONL file.

        Args:
            documents: List of case documents
            filename: Output filename
        """
        output_path = self.output_dir / filename

        with open(output_path, "w", encoding="utf-8") as f:
            for doc in documents:
                f.write(json.dumps(doc, ensure_ascii=False) + "\n")

        logger.info(f"Saved {len(documents)} case documents to {output_path}")

    def load_documents(self, filename: str = "cases.jsonl") -> List[Dict[str, Any]]:
        """
        Load documents from JSONL file.

        Args:
            filename: Input filename

        Returns:
            List of case documents
        """
        input_path = self.output_dir / filename

        if not input_path.exists():
            logger.warning(f"File not found: {input_path}")
            return []

        documents = []
        with open(input_path, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    documents.append(json.loads(line))

        logger.info(f"Loaded {len(documents)} case documents from {input_path}")
        return documents


def main():
    """Test crawler functionality."""
    crawler = OpenJurCrawler()

    # Crawl sample cases from BGH
    documents = crawler.crawl_court_cases("BGH", max_cases=5)

    # Save to file
    if documents:
        crawler.save_documents(documents)

        # Print sample
        print(f"\n=== Sample Case Document ===")
        print(json.dumps(documents[0], indent=2, ensure_ascii=False))
    else:
        logger.warning("No documents crawled. OpenJur API may require authentication or has changed.")

        # Create mock data for testing
        mock_doc = {
            "doc_id": "BGH-I-ZR-123-20",
            "title": "Schadensersatzanspruch bei Vertragsverletzung",
            "text": "Leitsatz: Bei einer Vertragsverletzung kann ein Schadensersatzanspruch...",
            "url": "https://openjur.de/mock",
            "type": "case",
            "jurisdiction": "DE",
            "court": "BGH",
            "case_id": "I ZR 123/20",
            "date": "2024-01-15",
            "court_name": "Bundesgerichtshof",
        }
        print(f"\n=== Mock Case Document (for testing) ===")
        print(json.dumps(mock_doc, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
