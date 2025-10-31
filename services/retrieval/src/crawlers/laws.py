"""
ABOUTME: Crawler for German laws from Gesetze-im-Internet.de.
ABOUTME: Extracts statutory text organized by sections (§) with metadata.
"""

import os
import json
import logging
import time
from typing import List, Dict, Any, Optional
from pathlib import Path
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LawsCrawler:
    """Crawler for Gesetze-im-Internet.de"""

    def __init__(self, base_url: Optional[str] = None, output_dir: Optional[str] = None):
        """
        Initialize laws crawler.

        Args:
            base_url: Base URL for Gesetze-im-Internet (defaults to env)
            output_dir: Directory to save raw data (defaults to data/raw/)
        """
        self.base_url = base_url or os.getenv(
            "GESETZE_IM_INTERNET_BASE_URL", "https://www.gesetze-im-internet.de"
        )
        self.output_dir = Path(output_dir or "data/raw")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Most important German laws for initial prototype
        self.important_laws = {
            "bgb": "Bürgerliches Gesetzbuch",
            "stgb": "Strafgesetzbuch",
            "gg": "Grundgesetz",
            "zpo": "Zivilprozessordnung",
            "stpo": "Strafprozessordnung",
            "hgb": "Handelsgesetzbuch",
            "arbeitsgesetze": "Arbeitsgesetze",
            "baugb": "Baugesetzbuch",
            "betrvg": "Betriebsverfassungsgesetz",
            "bverfgg": "Bundesverfassungsgerichtsgesetz",
        }

        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "JuraGPT-Research/1.0 (Educational/Research Purpose)",
            }
        )

    def crawl_law(self, law_id: str, law_name: str, max_sections: int = 50) -> List[Dict[str, Any]]:
        """
        Crawl a single law and extract sections.

        Args:
            law_id: Law identifier (e.g., "bgb", "stgb")
            law_name: Full name of the law
            max_sections: Maximum number of sections to crawl (for prototype)

        Returns:
            List of document dictionaries
        """
        logger.info(f"Crawling {law_name} ({law_id})...")

        documents = []
        law_url = f"{self.base_url}/{law_id}"

        try:
            # Get table of contents
            response = self.session.get(f"{law_url}/index.html", timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, "lxml")

            # Find section links (different structure for different laws)
            section_links = self._extract_section_links(soup, law_id)

            logger.info(f"Found {len(section_links)} sections in {law_name}")

            # Limit sections for prototype
            section_links = section_links[:max_sections]

            # Crawl each section
            for idx, (section_id, section_title, section_path) in enumerate(section_links):
                try:
                    section_url = f"{law_url}/{section_path}"
                    section_data = self._crawl_section(
                        law_id=law_id,
                        law_name=law_name,
                        section_id=section_id,
                        section_title=section_title,
                        section_url=section_url,
                    )

                    if section_data:
                        documents.append(section_data)

                    # Rate limiting
                    if idx % 10 == 0:
                        time.sleep(1)

                except Exception as e:
                    logger.warning(f"Error crawling section {section_id}: {e}")
                    continue

            logger.info(f"Crawled {len(documents)} sections from {law_name}")
            return documents

        except Exception as e:
            logger.error(f"Error crawling {law_name}: {e}")
            return []

    def _extract_section_links(
        self, soup: BeautifulSoup, law_id: str
    ) -> List[tuple[str, str, str]]:
        """
        Extract section links from table of contents.

        Returns:
            List of (section_id, section_title, section_path) tuples
        """
        section_links = []

        # Try different selectors based on page structure
        # Pattern 1: Direct links in TOC
        toc_links = soup.select("a[href*='__']")

        for link in toc_links:
            href = link.get("href", "")
            text = link.get_text(strip=True)

            if not href or not text:
                continue

            # Extract section identifier (e.g., "__823" from "__823.html")
            if "__" in href:
                section_id = href.split("__")[1].replace(".html", "")
                section_path = href

                # Title usually format: "§ 823 Schadensersatzpflicht"
                section_title = text

                section_links.append((section_id, section_title, section_path))

        return section_links

    def _crawl_section(
        self,
        law_id: str,
        law_name: str,
        section_id: str,
        section_title: str,
        section_url: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Crawl a single section and extract text.

        Returns:
            Document dictionary with metadata
        """
        try:
            response = self.session.get(section_url, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, "lxml")

            # Extract section text (usually in div.jnhtml or div.jurAbsatz)
            text_elements = soup.select("div.jnhtml, div.jurAbsatz, div.jnenbez, p")

            if not text_elements:
                logger.warning(f"No text found for {section_id}")
                return None

            # Combine text from all elements
            section_text = "\n\n".join(
                elem.get_text(strip=True) for elem in text_elements if elem.get_text(strip=True)
            )

            if not section_text or len(section_text) < 20:
                logger.warning(f"Section {section_id} has insufficient text")
                return None

            # Create document
            doc = {
                "doc_id": f"{law_id}-{section_id}",
                "title": section_title,
                "text": section_text,
                "url": section_url,
                "type": "statute",
                "jurisdiction": "DE",
                "law": law_id.upper(),
                "section": section_id,
                "law_name": law_name,
            }

            return doc

        except Exception as e:
            logger.error(f"Error crawling section {section_id} from {section_url}: {e}")
            return None

    def crawl_all(self, max_laws: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Crawl all important laws.

        Args:
            max_laws: Limit number of laws (for testing)

        Returns:
            List of all documents
        """
        all_documents = []
        laws_to_crawl = list(self.important_laws.items())

        if max_laws:
            laws_to_crawl = laws_to_crawl[:max_laws]

        for law_id, law_name in laws_to_crawl:
            docs = self.crawl_law(law_id, law_name)
            all_documents.extend(docs)

            # Rate limiting between laws
            time.sleep(2)

        logger.info(f"Total documents crawled: {len(all_documents)}")
        return all_documents

    def save_documents(self, documents: List[Dict[str, Any]], filename: str = "laws.jsonl"):
        """
        Save documents to JSONL file.

        Args:
            documents: List of document dictionaries
            filename: Output filename
        """
        output_path = self.output_dir / filename

        with open(output_path, "w", encoding="utf-8") as f:
            for doc in documents:
                f.write(json.dumps(doc, ensure_ascii=False) + "\n")

        logger.info(f"Saved {len(documents)} documents to {output_path}")

    def load_documents(self, filename: str = "laws.jsonl") -> List[Dict[str, Any]]:
        """
        Load documents from JSONL file.

        Args:
            filename: Input filename

        Returns:
            List of documents
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

        logger.info(f"Loaded {len(documents)} documents from {input_path}")
        return documents


def main():
    """Test crawler functionality."""
    crawler = LawsCrawler()

    # Crawl first 2 laws with limited sections for testing
    documents = crawler.crawl_all(max_laws=2)

    # Save to file
    crawler.save_documents(documents)

    # Print sample
    if documents:
        print(f"\n=== Sample Document ===")
        print(json.dumps(documents[0], indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
