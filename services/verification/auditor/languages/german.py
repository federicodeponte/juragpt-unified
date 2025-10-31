"""
ABOUTME: German language module for NLP processing
ABOUTME: Provides German-specific text normalization and spaCy model configuration
"""

from typing import Dict
from auditor.languages.base import BaseLanguageModule


class GermanLanguageModule(BaseLanguageModule):
    """
    German language module.

    Provides:
    - German spaCy model (de_core_news_md)
    - German-specific text normalization
    - German abbreviation expansions
    """

    def get_spacy_model(self) -> str:
        """Return German spaCy model name."""
        return "de_core_news_md"

    def normalize_text(self, text: str) -> str:
        """
        Normalize German text.

        Handles:
        - Quotation marks
        - Dashes
        - German paragraph symbols (§§)

        Args:
            text: Raw German text

        Returns:
            Normalized text
        """
        import re

        # Remove extra whitespace
        text = re.sub(r"\s+", " ", text).strip()

        # Normalize quotation marks
        text = text.replace("\u201E", '"').replace("\u201C", '"')
        text = text.replace("\u201A", "'").replace("\u2018", "'")

        # Normalize dashes
        text = text.replace("\u2013", "-").replace("\u2014", "-")

        # Fix multiple paragraph symbols
        text = text.replace("\u00A7\u00A7", "\u00A7 ")

        return text

    def get_abbreviation_mappings(self) -> Dict[str, str]:
        """
        Return German abbreviation expansions.

        Returns:
            Dict of German abbreviations to full forms
        """
        return {
            "Abs.": "Absatz",              # Paragraph
            "i.V.m.": "in Verbindung mit",  # in connection with
            "ggf.": "gegebenenfalls",      # if applicable
            "z.B.": "zum Beispiel",        # for example
            "u.a.": "unter anderem",       # among others
            "bzw.": "beziehungsweise",     # respectively
        }
