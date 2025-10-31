"""
ABOUTME: Base abstract class for domain modules
ABOUTME: Defines interface for vertical-specific verification patterns
"""

from abc import ABC, abstractmethod
from typing import List


class BaseDomain(ABC):
    """
    Abstract base class for domain modules.

    Domain modules provide vertical-specific knowledge:
    - Citation patterns (legal: §123, medical: ICD-10 codes, etc.)
    - Domain keywords (legal: "haftet", medical: "diagnosis", etc.)
    - Domain-specific validation logic

    Each vertical (Legal, Medical, Financial, etc.) implements this interface.
    Subdomains (GermanLegal, USLegal) extend the base vertical.
    """

    @abstractmethod
    def get_citation_patterns(self) -> List[str]:
        r"""
        Return regex patterns for domain citations.

        Examples:
            Legal: [r"§\s*\d+", r"Art\.\s*\d+"]
            Medical: [r"ICD-10:\s*[A-Z]\d+", r"CPT:\s*\d{5}"]

        Returns:
            List of regex patterns
        """
        pass

    @abstractmethod
    def get_domain_keywords(self) -> List[str]:
        """
        Return domain-specific keywords for statement classification.

        Examples:
            Legal: ["liable", "entitled", "plaintiff"]
            Medical: ["diagnosis", "treatment", "symptom"]

        Returns:
            List of keywords
        """
        pass

    @abstractmethod
    def extract_citations(self, text: str) -> List[str]:
        """
        Extract domain citations from text.

        Args:
            text: Input text

        Returns:
            List of found citations (e.g., ["§ 823 BGB", "Art. 1 GG"])
        """
        pass

    @abstractmethod
    def is_domain_statement(self, sentence: str) -> bool:
        """
        Determine if a sentence is a domain-specific statement.

        Uses citations + keywords to classify.

        Args:
            sentence: Sentence text

        Returns:
            True if sentence appears to be domain-specific
        """
        pass

    def get_domain_name(self) -> str:
        """
        Return human-readable domain name.

        Returns:
            Domain name (e.g., "German Legal", "US Medical")
        """
        return self.__class__.__name__.replace("Domain", "")
