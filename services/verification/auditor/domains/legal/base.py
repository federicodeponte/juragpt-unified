"""
ABOUTME: Base legal domain class for all legal jurisdictions
ABOUTME: Provides common legal verification patterns shared across jurisdictions
"""

import re
from typing import List
from auditor.domains.base import BaseDomain


class LegalDomain(BaseDomain):
    """
    Base class for all legal domains.

    Provides common legal patterns that are shared across jurisdictions:
    - Generic citation detection logic
    - Legal statement classification framework

    Subclasses (GermanLegalDomain, USLegalDomain, etc.) provide
    jurisdiction-specific patterns and keywords.
    """

    def extract_citations(self, text: str) -> List[str]:
        """
        Extract legal citations using domain-specific patterns.

        Args:
            text: Input text

        Returns:
            List of unique citations found
        """
        citations = []
        patterns = self.get_citation_patterns()

        for pattern in patterns:
            matches = re.findall(pattern, text)
            citations.extend(matches)

        return list(set(citations))  # Remove duplicates

    def is_domain_statement(self, sentence: str) -> bool:
        """
        Determine if a sentence is a legal statement.

        Checks:
        1. Contains legal citations
        2. Contains legal keywords

        Args:
            sentence: Sentence text

        Returns:
            True if appears to be a legal statement
        """
        # Check for citations
        if self._has_citation(sentence):
            return True

        # Check for legal keywords
        keywords = self.get_domain_keywords()
        return any(keyword in sentence for keyword in keywords)

    def _has_citation(self, text: str) -> bool:
        """
        Check if text contains any legal citations.

        Args:
            text: Input text

        Returns:
            True if citations found
        """
        patterns = self.get_citation_patterns()
        return any(re.search(pattern, text) for pattern in patterns)
