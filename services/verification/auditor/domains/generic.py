"""
ABOUTME: Generic domain module with no vertical-specific patterns
ABOUTME: Provides basic verification without domain-specific knowledge
"""

from typing import List
from auditor.domains.base import BaseDomain


class GenericDomain(BaseDomain):
    """
    Generic domain module - no vertical-specific patterns.

    Use this when:
    - Testing the system without domain knowledge
    - Verifying general content (not legal, medical, etc.)
    - Baseline verification without specialized patterns

    This module provides NO citations or keywords.
    Verification relies purely on semantic similarity.
    """

    def get_citation_patterns(self) -> List[str]:
        """
        Return empty - no domain-specific citation patterns.

        Returns:
            Empty list
        """
        return []

    def get_domain_keywords(self) -> List[str]:
        """
        Return empty - no domain-specific keywords.

        Returns:
            Empty list
        """
        return []

    def extract_citations(self, text: str) -> List[str]:
        """
        Return empty - no citations to extract.

        Args:
            text: Input text

        Returns:
            Empty list
        """
        return []

    def is_domain_statement(self, sentence: str) -> bool:
        """
        Always return False - no domain classification.

        Args:
            sentence: Sentence text

        Returns:
            False (not domain-specific)
        """
        return False

    def get_domain_name(self) -> str:
        """Return human-readable name."""
        return "Generic (No Domain)"
