"""
ABOUTME: Base abstract class for language modules
ABOUTME: Defines interface for language-specific text processing
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any


class BaseLanguageModule(ABC):
    """
    Abstract base class for language modules.

    Language modules provide language-specific NLP capabilities:
    - Sentence splitting
    - Text normalization
    - spaCy model selection

    Each language (German, English, etc.) implements this interface.
    """

    @abstractmethod
    def get_spacy_model(self) -> str:
        """
        Return the spaCy model name for this language.

        Returns:
            Model name (e.g., "de_core_news_md", "en_core_web_md")
        """
        pass

    @abstractmethod
    def normalize_text(self, text: str) -> str:
        """
        Normalize text with language-specific rules.

        Args:
            text: Raw input text

        Returns:
            Normalized text
        """
        pass

    @abstractmethod
    def get_abbreviation_mappings(self) -> Dict[str, str]:
        """
        Return language-specific abbreviation expansions.

        Returns:
            Dict mapping abbreviations to full forms
        """
        pass

    def split_sentences_basic(self, text: str, min_length: int = 3) -> List[str]:
        """
        Basic sentence splitting fallback (language-agnostic).

        Uses simple rules (., !, ?) when spaCy is not available.

        Args:
            text: Input text
            min_length: Minimum sentence length

        Returns:
            List of sentences
        """
        import re

        # Simple sentence boundary detection
        sentences = re.split(r'[.!?]+\s+', text)
        return [s.strip() for s in sentences if len(s.strip()) >= min_length]
