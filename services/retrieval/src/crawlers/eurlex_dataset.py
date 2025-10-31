"""
ABOUTME: EUR-Lex dataset loader for EU legal documents.
ABOUTME: Fetches German-language EU legal documents from EUR-Lex using CELEX IDs.
"""

import os
import json
import logging
import zipfile
import requests
import time
from pathlib import Path
from typing import List, Dict, Any, Optional
from tqdm import tqdm

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EURLexDataset:
    """Loader for EURLEX57K dataset of EU legal documents."""

    DATASET_URL = "http://nlp.cs.aueb.gr/software_and_datasets/EURLEX57K/datasets.zip"
    DATASET_DIR = "data/eurlex"

    def __init__(self, data_dir: Optional[str] = None):
        """
        Initialize EUR-Lex dataset loader.

        Args:
            data_dir: Directory to store dataset (default: data/eurlex)
        """
        self.data_dir = Path(data_dir or self.DATASET_DIR)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.dataset_zip = self.data_dir / "datasets.zip"
        self.extract_dir = self.data_dir / "EURLEX57K"

    def download_dataset(self, force: bool = False) -> bool:
        """
        Download EURLEX57K dataset if not already present.

        Args:
            force: Force re-download even if file exists

        Returns:
            True if downloaded, False if skipped (already exists)
        """
        if self.dataset_zip.exists() and not force:
            logger.info(f"Dataset already downloaded at {self.dataset_zip}")
            return False

        logger.info(f"Downloading EURLEX57K dataset from {self.DATASET_URL}")

        try:
            response = requests.get(self.DATASET_URL, stream=True, timeout=300)
            response.raise_for_status()

            total_size = int(response.headers.get('content-length', 0))

            with open(self.dataset_zip, 'wb') as f:
                with tqdm(total=total_size, unit='B', unit_scale=True, desc="Downloading") as pbar:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            pbar.update(len(chunk))

            logger.info(f"Downloaded dataset to {self.dataset_zip}")
            return True

        except Exception as e:
            logger.error(f"Failed to download dataset: {e}")
            if self.dataset_zip.exists():
                self.dataset_zip.unlink()
            raise

    def extract_dataset(self, force: bool = False) -> bool:
        """
        Extract dataset ZIP file.

        Args:
            force: Force re-extraction even if directory exists

        Returns:
            True if extracted, False if skipped
        """
        if self.extract_dir.exists() and not force:
            logger.info(f"Dataset already extracted at {self.extract_dir}")
            return False

        if not self.dataset_zip.exists():
            raise FileNotFoundError(f"Dataset ZIP not found at {self.dataset_zip}. Run download_dataset() first.")

        logger.info(f"Extracting dataset to {self.extract_dir}")

        try:
            with zipfile.ZipFile(self.dataset_zip, 'r') as zip_ref:
                zip_ref.extractall(self.extract_dir)

            # Remove __MACOSX directory if present
            macosx_dir = self.extract_dir / "__MACOSX"
            if macosx_dir.exists():
                import shutil
                shutil.rmtree(macosx_dir)

            logger.info(f"Extracted dataset to {self.extract_dir}")
            return True

        except Exception as e:
            logger.error(f"Failed to extract dataset: {e}")
            raise

    def _detect_language(self, text: str) -> str:
        """
        Simple language detection for German.

        Args:
            text: Text sample to check

        Returns:
            "de" if German, "other" otherwise
        """
        if not text or len(text) < 50:
            return "other"

        # Common German words and patterns
        german_indicators = [
            'der', 'die', 'das', 'und', 'für', 'auf', 'mit', 'wird',
            'können', 'müssen', 'soll', 'nach', 'über', 'durch',
            'Artikel', 'Verordnung', 'Richtlinie', 'gemäß', 'sowie'
        ]

        # Count German indicator words in first 500 chars
        sample = text[:500].lower()
        german_count = sum(1 for word in german_indicators if f' {word} ' in f' {sample} ')

        # If we find 3+ German indicators, consider it German
        return "de" if german_count >= 3 else "other"

    def load_documents(
        self,
        limit: Optional[int] = None,
        language: str = "EN"
    ) -> List[Dict[str, Any]]:
        """
        Load and parse EUR-Lex documents from extracted dataset.

        NOTE: EUR-LEX57K dataset is in English. For German versions,
        we would need to fetch them separately via EUR-Lex API using CELEX IDs.

        Args:
            limit: Maximum number of documents to load (None = all)
            language: Language code (currently only "EN" available in dataset)

        Returns:
            List of normalized document dictionaries
        """
        if not self.extract_dir.exists():
            raise FileNotFoundError(
                f"Dataset not extracted at {self.extract_dir}. "
                "Run extract_dataset() first."
            )

        # Find all JSON files in dataset directory
        json_files = list(self.extract_dir.rglob("*.json"))

        if not json_files:
            logger.warning(f"No JSON files found in {self.extract_dir}")
            return []

        logger.info(f"Found {len(json_files)} JSON files in dataset")

        documents = []

        for json_file in tqdm(json_files[:limit] if limit else json_files, desc="Loading EUR-Lex docs"):
            try:
                doc = self._parse_eurlex_json(json_file)

                if doc:
                    documents.append(doc)

                    if limit and len(documents) >= limit:
                        break

            except Exception as e:
                logger.warning(f"Failed to parse {json_file.name}: {e}")
                continue

        logger.info(f"Loaded {len(documents)} EUR-Lex documents (English)")

        return documents

    def _parse_eurlex_json(self, json_path: Path) -> Optional[Dict[str, Any]]:
        """
        Parse a single EUR-Lex JSON file.

        Args:
            json_path: Path to JSON file

        Returns:
            Normalized document dictionary or None if parsing fails
        """
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            logger.warning(f"Failed to read {json_path}: {e}")
            return None

        # Extract sections
        sections = []

        if 'header' in data and data['header']:
            sections.append(data['header'])

        if 'recitals' in data and data['recitals']:
            sections.append(data['recitals'])

        if 'main_body' in data and isinstance(data['main_body'], list):
            sections.extend(data['main_body'])

        if 'attachments' in data and data['attachments']:
            sections.append(data['attachments'])

        # Combine all sections
        text = '\n\n'.join(str(s) for s in sections if s)

        if len(text) < 100:
            return None

        # Extract metadata
        doc_id = json_path.stem  # Filename without extension

        # Get concepts/tags if available
        concepts = data.get('concepts', [])

        # Determine document type from concepts or filename
        doc_type = "eu_regulation"
        if any('directive' in str(c).lower() for c in concepts):
            doc_type = "eu_directive"
        elif any('decision' in str(c).lower() for c in concepts):
            doc_type = "eu_decision"

        return {
            "doc_id": f"eurlex-{doc_id}",
            "title": f"EUR-Lex {doc_id}",
            "text": text,
            "url": f"https://eur-lex.europa.eu/legal-content/DE/ALL/?uri=CELEX:{doc_id}",
            "type": doc_type,
            "jurisdiction": "EU",
            "concepts": concepts[:10] if concepts else [],  # Limit to 10 concepts
        }


def main():
    """Test the EUR-Lex dataset loader."""
    loader = EURLexDataset()

    # Download and extract dataset
    logger.info("Step 1: Downloading dataset...")
    loader.download_dataset()

    logger.info("\nStep 2: Extracting dataset...")
    loader.extract_dataset()

    # Load first 100 documents (English EUR-Lex documents)
    logger.info("\nStep 3: Loading documents...")
    docs = loader.load_documents(limit=100)

    if docs:
        logger.info(f"\nSuccessfully loaded {len(docs)} documents")
        logger.info(f"\nSample document:")
        logger.info(f"  Title: {docs[0]['title']}")
        logger.info(f"  CELEX ID: {docs[0]['doc_id']}")
        logger.info(f"  Type: {docs[0]['type']}")
        logger.info(f"  Text length: {len(docs[0]['text'])} characters")
        logger.info(f"  URL: {docs[0]['url']}")
    else:
        logger.warning("No documents loaded")


if __name__ == "__main__":
    main()
