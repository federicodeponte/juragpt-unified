"""
ABOUTME: Text normalization utilities for legal documents.
ABOUTME: Cleans HTML artifacts, normalizes whitespace, and prepares text for embedding.
"""

import re
import logging
from typing import List, Dict, Any
import unicodedata

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TextNormalizer:
    """Normalizes legal text for processing and embedding."""

    def __init__(self):
        """Initialize normalizer with cleaning patterns."""
        # HTML entities and artifacts
        self.html_patterns = [
            (r"&nbsp;", " "),
            (r"&amp;", "&"),
            (r"&lt;", "<"),
            (r"&gt;", ">"),
            (r"&quot;", '"'),
            (r"&apos;", "'"),
            (r"<[^>]+>", ""),  # Remove HTML tags
        ]

        # Whitespace patterns
        self.whitespace_patterns = [
            (r"\r\n", "\n"),  # Normalize line endings
            (r"\r", "\n"),
            (r"\t", " "),  # Convert tabs to spaces
            (r" +", " "),  # Collapse multiple spaces
            (r"\n{3,}", "\n\n"),  # Max 2 consecutive newlines
        ]

        # Legal document specific patterns
        self.legal_patterns = [
            (r"\((\d+)\)", r"(\1)"),  # Normalize parentheses around numbers
            (r"§\s+(\d+)", r"§\1"),  # Normalize § spacing
            (r"Abs\.\s+(\d+)", r"Abs. \1"),  # Normalize Absatz
            (r"Nr\.\s+(\d+)", r"Nr. \1"),  # Normalize Nummer
        ]

    def normalize(self, text: str) -> str:
        """
        Normalize text through all cleaning stages.

        Args:
            text: Raw text to normalize

        Returns:
            Cleaned and normalized text
        """
        if not text:
            return ""

        # 1. Unicode normalization (NFC form)
        text = unicodedata.normalize("NFC", text)

        # 2. Remove HTML entities and tags
        text = self._apply_patterns(text, self.html_patterns)

        # 3. Normalize whitespace
        text = self._apply_patterns(text, self.whitespace_patterns)

        # 4. Legal document specific normalization
        text = self._apply_patterns(text, self.legal_patterns)

        # 5. Strip leading/trailing whitespace
        text = text.strip()

        return text

    def _apply_patterns(self, text: str, patterns: List[tuple[str, str]]) -> str:
        """
        Apply regex replacement patterns.

        Args:
            text: Text to process
            patterns: List of (pattern, replacement) tuples

        Returns:
            Processed text
        """
        for pattern, replacement in patterns:
            text = re.sub(pattern, replacement, text)
        return text

    def normalize_document(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize text fields in a document dictionary.

        Args:
            doc: Document dictionary with 'text' and optionally 'title'

        Returns:
            Document with normalized text fields
        """
        normalized_doc = doc.copy()

        # Normalize main text
        if "text" in normalized_doc:
            normalized_doc["text"] = self.normalize(normalized_doc["text"])

        # Normalize title
        if "title" in normalized_doc:
            normalized_doc["title"] = self.normalize(normalized_doc["title"])

        return normalized_doc

    def normalize_documents(self, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Normalize multiple documents.

        Args:
            documents: List of document dictionaries

        Returns:
            List of normalized documents
        """
        logger.info(f"Normalizing {len(documents)} documents...")

        normalized_docs = []
        for doc in documents:
            normalized_doc = self.normalize_document(doc)

            # Skip documents with insufficient text
            if len(normalized_doc.get("text", "")) < 20:
                logger.warning(f"Skipping document {doc.get('doc_id')} - insufficient text")
                continue

            normalized_docs.append(normalized_doc)

        logger.info(f"Normalized {len(normalized_docs)} documents")
        return normalized_docs

    @staticmethod
    def clean_legal_references(text: str) -> str:
        """
        Standardize legal references in text.

        Args:
            text: Text containing legal references

        Returns:
            Text with standardized references
        """
        # Standardize common legal abbreviations
        replacements = {
            r"\bBGB\b": "BGB",
            r"\bStGB\b": "StGB",
            r"\bGG\b": "GG",
            r"\bZPO\b": "ZPO",
            r"\bStPO\b": "StPO",
        }

        for pattern, replacement in replacements.items():
            text = re.sub(pattern, replacement, text)

        return text


def main():
    """Test normalizer functionality."""
    normalizer = TextNormalizer()

    # Test cases
    test_texts = [
        "§  823  Abs.  1  BGB",
        "&nbsp;&nbsp;Wer vorsätzlich&nbsp;oder fahrlässig...",
        "<p>Test   text    with     multiple     spaces</p>",
        "Line1\r\nLine2\r\nLine3",
    ]

    print("=== Text Normalization Tests ===\n")
    for i, text in enumerate(test_texts, 1):
        normalized = normalizer.normalize(text)
        print(f"Test {i}:")
        print(f"  Input:  {repr(text)}")
        print(f"  Output: {repr(normalized)}")
        print()


if __name__ == "__main__":
    main()
