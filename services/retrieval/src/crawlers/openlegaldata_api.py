"""
ABOUTME: OpenLegalData API client for fetching German court cases and laws.
ABOUTME: Handles pagination, rate limiting, and data normalization.
"""

import requests
import logging
import time
from typing import List, Optional
from bs4 import BeautifulSoup

from src.models.document import CaseDocument, StatuteDocument
from src.exceptions import (
    APIConnectionError,
    APIResponseError,
    RateLimitExceededError,
    DocumentValidationError,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OpenLegalDataAPI:
    """Client for OpenLegalData.io REST API."""

    BASE_URL = "https://de.openlegaldata.io/api"

    def __init__(self, rate_limit_delay: float = 0.5):
        """
        Initialize API client.

        Args:
            rate_limit_delay: Delay between requests in seconds (default: 0.5s = 2 req/s)
        """
        self.rate_limit_delay = rate_limit_delay
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "JuraGPT-RAG/1.0 (Educational Research Project)"
        })

    def _make_request(self, url: str, params: Optional[dict] = None) -> dict:
        """Make API request with rate limiting and error handling."""
        time.sleep(self.rate_limit_delay)

        try:
            response = self.session.get(url, params=params, timeout=30)

            # Handle rate limiting
            if response.status_code == 429:
                retry_after = int(response.headers.get("Retry-After", 60))
                raise RateLimitExceededError("OpenLegalData", retry_after=retry_after)

            response.raise_for_status()
            return response.json()

        except requests.exceptions.Timeout as e:
            raise APIConnectionError(
                "OpenLegalData",
                url,
                reason="Request timeout"
            ) from e
        except requests.exceptions.ConnectionError as e:
            raise APIConnectionError(
                "OpenLegalData",
                url,
                reason="Connection failed"
            ) from e
        except requests.exceptions.HTTPError as e:
            raise APIResponseError(
                "OpenLegalData",
                status_code=response.status_code,
                response_body=response.text[:200]
            ) from e
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {e}")
            raise

    def fetch_cases(
        self,
        limit: Optional[int] = None,
        max_pages: int = 10,
        created_date_gte: Optional[str] = None,
    ) -> List[CaseDocument]:
        """
        Fetch court cases from OpenLegalData API.

        Args:
            limit: Maximum number of cases to fetch (None = fetch all up to max_pages)
            max_pages: Maximum number of pages to paginate through
            created_date_gte: Filter cases created on or after this date (ISO format: YYYY-MM-DD)

        Returns:
            List of normalized case documents
        """
        logger.info(
            f"Fetching court cases from OpenLegalData API "
            f"(limit={limit}, max_pages={max_pages}, created_date_gte={created_date_gte})"
        )

        cases = []
        url = f"{self.BASE_URL}/cases/"
        page = 1

        # Build query parameters
        params: dict = {"page": page}
        if created_date_gte:
            params["created_date__gte"] = created_date_gte

        while page <= max_pages:
            logger.info(f"Fetching cases page {page}...")

            try:
                params["page"] = page
                data = self._make_request(url, params=params)
            except Exception as e:
                logger.warning(f"Failed to fetch page {page}: {e}")
                break

            results = data.get("results", [])
            if not results:
                logger.info("No more results")
                break

            for case_data in results:
                case_doc = self._normalize_case(case_data)
                if case_doc:
                    cases.append(case_doc)

                if limit and len(cases) >= limit:
                    logger.info(f"Reached limit of {limit} cases")
                    return cases

            # Check for next page
            if not data.get("next"):
                logger.info("No more pages available")
                break

            page += 1

        logger.info(f"Successfully fetched {len(cases)} court cases")
        return cases

    def fetch_laws(
        self,
        limit: Optional[int] = None,
        max_pages: int = 10,
        created_date_gte: Optional[str] = None,
    ) -> List[StatuteDocument]:
        """
        Fetch laws from OpenLegalData API.

        Args:
            limit: Maximum number of laws to fetch (None = fetch all up to max_pages)
            max_pages: Maximum number of pages to paginate through
            created_date_gte: Filter laws created on or after this date (ISO format: YYYY-MM-DD)

        Returns:
            List of normalized law documents
        """
        logger.info(
            f"Fetching laws from OpenLegalData API "
            f"(limit={limit}, max_pages={max_pages}, created_date_gte={created_date_gte})"
        )

        laws = []
        url = f"{self.BASE_URL}/laws/"
        page = 1

        # Build query parameters
        params: dict = {"page": page}
        if created_date_gte:
            params["created_date__gte"] = created_date_gte

        while page <= max_pages:
            logger.info(f"Fetching laws page {page}...")

            try:
                params["page"] = page
                data = self._make_request(url, params=params)
            except Exception as e:
                logger.warning(f"Failed to fetch page {page}: {e}")
                break

            results = data.get("results", [])
            if not results:
                logger.info("No more results")
                break

            for law_data in results:
                law_doc = self._normalize_law(law_data)
                if law_doc:
                    laws.append(law_doc)

                if limit and len(laws) >= limit:
                    logger.info(f"Reached limit of {limit} laws")
                    return laws

            # Check for next page
            if not data.get("next"):
                logger.info("No more pages available")
                break

            page += 1

        logger.info(f"Successfully fetched {len(laws)} laws")
        return laws

    def _normalize_case(self, case_data: dict) -> Optional[CaseDocument]:
        """
        Normalize case data to our document format.

        Expected API format:
        {
            "slug": "bverwg-2013-11-14-7-c-217",
            "court": {"name": "Bundesverwaltungsgericht", "slug": "bverwg"},
            "file_number": "7 C 2.17",
            "date": "2013-11-14",
            "type": "Urteil",
            "content": "<html>...</html>"
        }
        """
        try:
            # Extract text from HTML content
            content_html = case_data.get("content", "")
            if content_html:
                soup = BeautifulSoup(content_html, "lxml")
                text_content = soup.get_text(separator="\n", strip=True)
            else:
                text_content = ""

            # Skip if no meaningful content
            # Threshold of 50 chars to avoid losing short but meaningful cases
            min_chars = 50
            if len(text_content) < min_chars:
                logger.debug(
                    f"Skipping case {case_data.get('slug')}: "
                    f"content too short ({len(text_content)} chars < {min_chars})"
                )
                return None

            court = case_data.get("court", {})
            court_name = court.get("name", "Unknown Court")
            court_slug = court.get("slug", "unknown")

            return {
                "doc_id": case_data.get("slug", f"case-{case_data.get('id')}"),
                "title": f"{court_name} - {case_data.get('file_number', 'N/A')} - {case_data.get('date', 'N/A')}",
                "text": text_content,
                "url": f"https://de.openlegaldata.io/case/{case_data.get('slug', '')}",
                "type": "case",
                "jurisdiction": "DE",
                "court": court_slug.upper(),
                "case_id": case_data.get("file_number"),
                "date": case_data.get("date"),
                "decision_type": case_data.get("type"),
            }
        except Exception as e:
            logger.error(f"Error normalizing case: {e}")
            return None

    def _normalize_law(self, law_data: dict) -> Optional[StatuteDocument]:
        """
        Normalize law data to our document format.

        Expected API format:
        {
            "slug": "bgb",
            "title": "Bürgerliches Gesetzbuch",
            "abbreviation": "BGB",
            "content": "<html>...</html>",
            "latest_date": "2023-01-01"
        }
        """
        try:
            # Extract text from HTML content
            content_html = law_data.get("content", "")
            if content_html:
                soup = BeautifulSoup(content_html, "lxml")
                text_content = soup.get_text(separator="\n", strip=True)
            else:
                text_content = law_data.get("text", "")

            # Skip if no meaningful content
            # Lower threshold to 50 chars to avoid losing legal basis citations
            # (e.g., "eingangsformel" sections with 80-333 chars)
            min_chars = 50
            if len(text_content) < min_chars:
                logger.debug(
                    f"Skipping law {law_data.get('slug')}: "
                    f"content too short ({len(text_content)} chars < {min_chars})"
                )
                return None

            abbreviation = law_data.get("abbreviation", law_data.get("slug", "Unknown").upper())
            title = law_data.get("title", abbreviation)

            return {
                "doc_id": law_data.get("slug", f"law-{law_data.get('id')}"),
                "title": f"{abbreviation} - {title}",
                "text": text_content,
                "url": f"https://de.openlegaldata.io/law/{law_data.get('slug', '')}",
                "type": "statute",
                "jurisdiction": "DE",
                "law": abbreviation,
                "date": law_data.get("latest_date"),
            }
        except Exception as e:
            logger.error(f"Error normalizing law: {e}")
            return None


def main():
    """Test the API client."""
    api = OpenLegalDataAPI()

    # Test fetching 5 cases
    logger.info("Testing case fetching...")
    cases = api.fetch_cases(limit=5, max_pages=1)
    logger.info(f"Fetched {len(cases)} cases")
    if cases:
        logger.info(f"Sample case: {cases[0]['title']}")

    # Test fetching 5 laws
    logger.info("\nTesting law fetching...")
    laws = api.fetch_laws(limit=5, max_pages=1)
    logger.info(f"Fetched {len(laws)} laws")
    if laws:
        logger.info(f"Sample law: {laws[0]['title']}")


if __name__ == "__main__":
    main()
