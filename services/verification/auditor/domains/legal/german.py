"""
ABOUTME: German legal domain module for German law verification
ABOUTME: Provides German legal citation patterns and legal keywords
"""

from typing import List
from auditor.domains.legal.base import LegalDomain


class GermanLegalDomain(LegalDomain):
    """
    German legal domain module.

    Provides German-specific legal patterns:
    - German legal citations (§, Art., BGB, StGB, etc.)
    - German legal keywords (haftet, verpflichtet, etc.)
    - German court references (BGH, BVerfG, etc.)
    """

    def get_citation_patterns(self) -> List[str]:
        """
        Return German legal citation patterns.

        Patterns:
        - § 823 BGB (German paragraph symbol + law code)
        - Art. 1 GG (Article + law code)
        - BGH VI ZR 396/18 (German court decisions)

        Returns:
            List of regex patterns for German legal citations
        """
        return [
            # Paragraph references
            r"§\s*\d+",  # § 823

            # Articles
            r"Art\.\s*\d+",  # Art. 1

            # Paragraph + Absatz (paragraph subsection)
            r"Abs\.\s*\d+",  # Abs. 1

            # Law codes (simplified - matches common codes)
            r"\b(?:BGB|StGB|ZPO|GG|HGB|AktG|InsO|UrhG|PatG)\b",

            # German courts
            r"\b(?:BGH|BVerfG|BAG|BFH|BSG|BVerwG|VGH|OLG|LG|AG)\b",

            # Full court decisions (e.g., BGH VI ZR 396/18)
            r"(?:BGH|BVerfG|BAG|BFH|BSG|BVerwG)\s+[IVX]+\s+[A-Z]+\s+\d+/\d+",

            # Combined paragraph + law code (§ 823 BGB)
            r"§\s*\d+(?:\s+Abs\.\s*\d+)?(?:\s+[A-Z]{2,})?",

            # Combined article + law code (Art. 1 GG)
            r"Art\.\s*\d+(?:\s+Abs\.\s*\d+)?(?:\s+[A-Z]{2,})?",
        ]

    def get_domain_keywords(self) -> List[str]:
        """
        Return German legal keywords.

        These words indicate legal statements in German text.

        Returns:
            List of German legal keywords
        """
        return [
            # Liability / Obligations
            "haftet",           # is liable
            "verpflichtet",     # is obligated
            "schuldet",         # owes

            # Rights / Claims
            "Anspruch",         # claim/right
            "berechtigt",       # entitled
            "Recht",            # right
            "Pflicht",          # duty/obligation

            # Legal status / Effects
            "gilt",             # applies/is valid
            "ist zu",           # is to
            "muss",             # must
            "kann",             # may/can
            "darf",             # may/is allowed

            # Legal actions
            "klagen",           # to sue
            "Klage",            # lawsuit
            "Vertrag",          # contract
            "Haftung",          # liability

            # Decisions / Rulings
            "Urteil",           # judgment
            "Beschluss",        # decision/resolution
            "entschieden",      # decided

            # Legal relationships
            "Schuldner",        # debtor
            "Gläubiger",        # creditor
            "Kläger",           # plaintiff
            "Beklagter",        # defendant
        ]

    def get_domain_name(self) -> str:
        """Return human-readable name."""
        return "German Legal"
