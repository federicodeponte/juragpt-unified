"""
ABOUTME: Hierarchical document parser for German legal documents
ABOUTME: Extracts § sections, Absätze, Ziffern and builds parent-child relationships
"""

import re
import uuid
from dataclasses import dataclass
from typing import Dict, List, Optional, TypedDict

from app.config import settings
from app.db.models import ChunkType, Section


class SectionMarker(TypedDict):
    """Type definition for section markers during parsing"""

    start: int
    end: int
    section_id: str
    level: int
    chunk_type: ChunkType


@dataclass
class ParsedSection:
    """Internal representation of a parsed section"""

    section_id: str
    content: str
    level: int  # Hierarchy level (0=top, 1=subsection, etc.)
    position: int
    parent_position: Optional[int] = None
    chunk_type: ChunkType = ChunkType.SECTION


class DocumentParser:
    """
    Parse German legal documents into hierarchical structure
    Handles §, Absatz, Ziffer, and other legal markers
    """

    # German legal section patterns (ordered by hierarchy level)
    PATTERNS = [
        # Level 0: Main sections (supports subsections like §5.2, §12.3.4)
        (r"§\s*(\d+(?:\.\d+)*[a-z]?)\s*", ChunkType.SECTION, 0),
        (r"Artikel\s+(\d+(?:\.\d+)*[a-z]?)\s*", ChunkType.SECTION, 0),
        # Level 1: Subsections
        (r"Absatz\s+(\d+)", ChunkType.SUBSECTION, 1),
        (r"Abs\.\s*(\d+)", ChunkType.SUBSECTION, 1),
        # Level 2: Clauses
        (r"Ziffer\s+(\d+\.?\d*)", ChunkType.CLAUSE, 2),
        (r"Ziff\.\s*(\d+\.?\d*)", ChunkType.CLAUSE, 2),
        (r"Nr\.\s*(\d+\.?\d*)", ChunkType.CLAUSE, 2),
        (r"Nummer\s+(\d+\.?\d*)", ChunkType.CLAUSE, 2),
        # Level 3: Sub-clauses
        (r"Buchstabe\s+([a-z])", ChunkType.PARAGRAPH, 3),
        (r"lit\.\s*([a-z])", ChunkType.PARAGRAPH, 3),
        (r"\(([a-z])\)", ChunkType.PARAGRAPH, 3),
    ]

    def __init__(self, max_chunk_size: Optional[int] = None):
        self.max_chunk_size = max_chunk_size or settings.max_chunk_size
        self.chunk_overlap = settings.chunk_overlap

    def parse_document(self, text: str) -> List[Section]:
        """
        Parse document text into hierarchical sections

        Args:
            text: Raw document text

        Returns:
            List of Section objects with parent-child relationships
        """
        # 1. Clean and normalize text
        text = self._normalize_text(text)

        # 2. Extract all sections with their positions
        parsed_sections = self._extract_sections(text)

        # 3. Build hierarchy (parent-child relationships)
        sections_with_hierarchy = self._build_hierarchy(parsed_sections)

        # 4. Convert to Section models
        sections = self._to_section_models(sections_with_hierarchy)

        return sections

    def create_chunks_for_embedding(
        self, sections: List[Section], document_id: uuid.UUID
    ) -> List[Dict]:
        """
        Convert sections to embeddable chunks
        Splits large sections if needed

        Returns:
            List of chunk dictionaries ready for database insertion
        """
        chunks = []
        position = 0

        for section in sections:
            # If section is too large, split it
            if len(section.content) > self.max_chunk_size:
                split_chunks = self._split_large_section(section, position)
                chunks.extend(split_chunks)
                position += len(split_chunks)
            else:
                chunks.append(
                    {
                        "document_id": str(document_id),
                        "section_id": section.section_id,
                        "content": section.content,
                        "chunk_type": section.chunk_type.value,
                        "position": position,
                        "parent_id": None,  # Will be set during hierarchy building
                        "metadata": {
                            "char_count": len(section.content),
                            "word_count": len(section.content.split()),
                        },
                    }
                )
                position += 1

        return chunks

    def _normalize_text(self, text: str) -> str:
        """Normalize document text"""
        # Remove excessive whitespace
        text = re.sub(r"\s+", " ", text)
        # Remove page numbers and headers (common patterns)
        text = re.sub(r"Seite\s+\d+\s+von\s+\d+", "", text)
        # Normalize line breaks
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        return text.strip()

    def _extract_sections(self, text: str) -> List[ParsedSection]:
        """
        Extract all sections with their markers
        Returns list of ParsedSection with positions
        """
        sections: List[ParsedSection] = []
        position = 0

        # Find all section markers and their positions
        markers: List[SectionMarker] = []
        for pattern, chunk_type, level in self.PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                marker: SectionMarker = {
                    "start": match.start(),
                    "end": match.end(),
                    "section_id": match.group(0).strip(),
                    "level": level,
                    "chunk_type": chunk_type,
                }
                markers.append(marker)

        # Sort by position in document
        markers.sort(key=lambda x: x["start"])

        # Extract content between markers
        for i, marker in enumerate(markers):
            # Content starts after current marker
            content_start = marker["end"]

            # Content ends at next marker (or end of document)
            content_end = markers[i + 1]["start"] if i + 1 < len(markers) else len(text)

            content = text[content_start:content_end].strip()

            # Skip empty sections
            if not content:
                continue

            sections.append(
                ParsedSection(
                    section_id=marker["section_id"],
                    content=content,
                    level=marker["level"],
                    position=position,
                    chunk_type=marker["chunk_type"],
                )
            )
            position += 1

        return sections

    def _build_hierarchy(self, sections: List[ParsedSection]) -> List[ParsedSection]:
        """
        Build parent-child relationships based on hierarchy levels

        A section's parent is the nearest preceding section with a lower level
        Example: "Abs. 2" (level 1) is child of "§5" (level 0)
        """
        for i, section in enumerate(sections):
            # Look backwards for parent (nearest section with lower level)
            for j in range(i - 1, -1, -1):
                if sections[j].level < section.level:
                    section.parent_position = sections[j].position
                    break

        return sections

    def _to_section_models(self, parsed_sections: List[ParsedSection]) -> List[Section]:
        """Convert ParsedSection to Section Pydantic models"""
        sections = []

        for ps in parsed_sections:
            section = Section(
                section_id=ps.section_id,
                content=ps.content,
                parent_id=None,  # Will be UUID later
                chunk_type=ps.chunk_type,
                position=ps.position,
            )
            sections.append(section)

        return sections

    def _split_large_section(self, section: Section, start_position: int) -> List[Dict]:
        """
        Split a large section into smaller chunks with overlap
        Maintains context by overlapping chunks
        """
        chunks = []
        content = section.content
        chunk_size = self.max_chunk_size
        overlap = self.chunk_overlap

        start = 0
        chunk_index = 0

        while start < len(content):
            # Calculate end position
            end = start + chunk_size

            # Try to break at sentence boundary
            if end < len(content):
                # Look for period followed by space
                sentence_end = content.rfind(". ", start, end)
                if sentence_end != -1:
                    end = sentence_end + 1

            chunk_content = content[start:end].strip()

            chunks.append(
                {
                    "section_id": f"{section.section_id}_{chunk_index}",
                    "content": chunk_content,
                    "chunk_type": section.chunk_type.value,
                    "position": start_position + chunk_index,
                    "metadata": {
                        "is_split": True,
                        "split_index": chunk_index,
                        "parent_section_id": section.section_id,
                    },
                }
            )

            # Move start position (with overlap)
            start = end - overlap if end < len(content) else len(content)
            chunk_index += 1

        return chunks

    def extract_section_numbers(self, text: str) -> List[str]:
        """
        Extract just the section numbers/IDs from text
        Useful for citation matching
        """
        section_ids = []

        for pattern, _, _ in self.PATTERNS:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                section_ids.append(match.group(0).strip())

        return list(set(section_ids))  # Unique section IDs
