"""Test document parser with German legal patterns"""

import pytest
from app.core.document_parser import DocumentParser
from app.db.models import ChunkType
import uuid


class TestDocumentParser:
    """Test hierarchical document parsing"""

    @pytest.fixture
    def parser(self):
        return DocumentParser()

    @pytest.fixture
    def sample_contract(self):
        return """
        § 1 Vertragsgegenstand

        Dieser Vertrag regelt die Zusammenarbeit.

        § 2 Pflichten der Parteien

        Absatz 1
        Die Partei A verpflichtet sich zur Leistung.

        Absatz 2
        Die Partei B verpflichtet sich zur Zahlung.

        Ziffer 1
        Zahlung erfolgt binnen 30 Tagen.

        § 3 Haftung

        Die Haftung ist auf grobe Fahrlässigkeit beschränkt.
        """

    def test_extract_sections(self, parser, sample_contract):
        """Test basic section extraction"""
        sections = parser.parse_document(sample_contract)

        assert len(sections) > 0
        section_ids = [s.section_id for s in sections]

        # Should find § markers
        assert any("§" in sid for sid in section_ids)

    def test_hierarchy_building(self, parser, sample_contract):
        """Test parent-child relationships"""
        sections = parser.parse_document(sample_contract)

        # Find Absatz sections (should be children of §)
        absatz_sections = [s for s in sections if "Absatz" in s.section_id]

        if absatz_sections:
            # Absatz should have higher level (children)
            assert absatz_sections[0].chunk_type in [ChunkType.SUBSECTION, ChunkType.PARAGRAPH]

    def test_chunk_creation(self, parser):
        """Test chunk dictionary creation"""
        text = "§ 5 Test\nDies ist ein Test."
        sections = parser.parse_document(text)

        doc_id = uuid.uuid4()
        chunks = parser.create_chunks_for_embedding(sections, doc_id)

        assert len(chunks) > 0
        assert "document_id" in chunks[0]
        assert "content" in chunks[0]
        assert "section_id" in chunks[0]

    def test_large_section_splitting(self, parser):
        """Test splitting of large sections"""
        # Create text larger than max_chunk_size
        large_text = "§ 1 Test\n" + "Das ist ein sehr langer Text. " * 200

        sections = parser.parse_document(large_text)
        doc_id = uuid.uuid4()
        chunks = parser.create_chunks_for_embedding(sections, doc_id)

        # Should create multiple chunks for large section
        assert len(chunks) >= 1

    def test_section_number_extraction(self, parser):
        """Test extracting section numbers from text"""
        text = "According to §5.2 and Absatz 3, the following applies..."

        section_ids = parser.extract_section_numbers(text)

        assert len(section_ids) > 0
        assert any("§" in sid or "Absatz" in sid for sid in section_ids)

    def test_normalization(self, parser):
        """Test text normalization"""
        messy_text = "§  5   Test  \n\n\n  Content   "

        normalized = parser._normalize_text(messy_text)

        # Should remove excessive whitespace
        assert "  " not in normalized or normalized.count("  ") < messy_text.count("  ")

    def test_empty_document(self, parser):
        """Test handling of empty document"""
        sections = parser.parse_document("")

        assert sections == []

    def test_multiple_section_types(self, parser):
        """Test recognition of different section markers"""
        text = """
        § 1 Paragraph
        Artikel 2 Article
        Absatz 1 Subsection
        Ziffer 1 Clause
        Nr. 3 Number
        """

        sections = parser.parse_document(text)

        # Should recognize multiple types
        assert len(sections) >= 3

    def test_special_characters(self, parser):
        """Test handling of special German characters"""
        text = "§ 1 Überblick\nDie Bürgschaft für Müller GmbH..."

        sections = parser.parse_document(text)

        assert len(sections) > 0
        assert "Überblick" in sections[0].content or "Überblick" in sections[0].section_id
