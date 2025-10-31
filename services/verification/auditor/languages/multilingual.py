"""
ABOUTME: Multilingual fallback language module
ABOUTME: Provides basic language-agnostic processing without spaCy
"""

from typing import Dict
from auditor.languages.base import BaseLanguageModule


class MultilingualModule(BaseLanguageModule):
    """
    Multilingual fallback module.

    Provides basic language-agnostic text processing.
    Does NOT use spaCy - uses simple sentence splitting.

    Use this when:
    - No language-specific model is available
    - Testing without spaCy dependencies
    - Processing any language without specialized support
    """

    def get_spacy_model(self) -> str:
        """
        Return None - this module doesn't use spaCy.

        Note: SentenceProcessor will fall back to basic splitting.
        """
        return ""  # Empty means no spaCy model

    def normalize_text(self, text: str) -> str:
        """
        Basic language-agnostic normalization.

        Args:
            text: Raw text

        Returns:
            Normalized text
        """
        import re

        # Remove extra whitespace
        text = re.sub(r"\s+", " ", text).strip()

        # Normalize quotation marks (universal)
        text = text.replace("\u201E", '"').replace("\u201C", '"')
        text = text.replace("\u201A", "'").replace("\u2018", "'")

        # Normalize dashes
        text = text.replace("\u2013", "-").replace("\u2014", "-")

        return text

    def get_abbreviation_mappings(self) -> Dict[str, str]:
        """
        Return empty - no language-specific abbreviations.

        Returns:
            Empty dict
        """
        return {}
