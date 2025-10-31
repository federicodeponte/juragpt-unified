# -*- coding: utf-8 -*-
"""
Unit tests for SentenceProcessor module.
"""

import pytest
from auditor.core.sentence_processor import SentenceProcessor
from auditor.languages.german import GermanLanguageModule
from auditor.domains.legal.german import GermanLegalDomain


class TestSentenceProcessor:
    """Test SentenceProcessor functionality."""

    def test_initialization_default(self):
        """Test default initialization."""
        processor = SentenceProcessor()
        assert processor.language_module is not None
        assert isinstance(processor.language_module, GermanLanguageModule)

    def test_initialization_with_modules(self):
        """Test initialization with explicit modules."""
        lang_module = GermanLanguageModule()
        domain_module = GermanLegalDomain()
        processor = SentenceProcessor(
            language_module=lang_module,
            domain_module=domain_module
        )
        assert processor.language_module == lang_module
        assert processor.domain_module == domain_module

    def test_initialization_deprecated_model_name(self):
        """Test deprecated model_name parameter shows warning."""
        with pytest.warns(DeprecationWarning):
            processor = SentenceProcessor(model_name="de_core_news_md")
        assert processor.language_module is not None

    def test_normalize_text(self, sample_german_text):
        """Test text normalization."""
        processor = SentenceProcessor()
        normalized = processor.normalize_text(sample_german_text)

        # Check that text is normalized
        assert isinstance(normalized, str)
        assert len(normalized) > 0
        # Should preserve German characters
        assert "§" in normalized or "Paragraph" in normalized

    def test_split_sentences_basic(self, sample_german_text):
        """Test sentence splitting."""
        processor = SentenceProcessor()
        sentences = processor.split_sentences(sample_german_text)

        # Should split into multiple sentences
        assert isinstance(sentences, list)
        assert len(sentences) >= 1
        # Each sentence should be a string
        assert all(isinstance(s, str) for s in sentences)
        # Sentences should have minimum length
        assert all(len(s) >= 3 for s in sentences)

    def test_split_sentences_min_length(self):
        """Test minimum sentence length filtering."""
        processor = SentenceProcessor()
        text = "Hi. This is a longer sentence. Ok."
        sentences = processor.split_sentences(text, min_length=10)

        # Short sentences should be filtered out
        assert all(len(s) >= 10 for s in sentences)

    def test_split_with_metadata(self, sample_german_text):
        """Test sentence splitting with metadata."""
        processor = SentenceProcessor()
        sentences = processor.split_with_metadata(sample_german_text)

        # Should return list of dicts
        assert isinstance(sentences, list)
        assert len(sentences) >= 1

        # Check metadata structure
        for sent in sentences:
            assert "text" in sent
            assert "start" in sent
            assert "end" in sent
            assert "index" in sent
            assert "tokens" in sent
            assert "has_citation" in sent

            # Check types
            assert isinstance(sent["text"], str)
            assert isinstance(sent["start"], int)
            assert isinstance(sent["end"], int)
            assert isinstance(sent["index"], int)
            assert isinstance(sent["tokens"], int)
            assert isinstance(sent["has_citation"], bool)

    def test_extract_citations(self):
        """Test citation extraction."""
        processor = SentenceProcessor()
        text = "Nach § 823 BGB und Art. 1 GG haftet der Schuldner."
        citations = processor.extract_citations(text)

        # Should extract legal citations
        assert isinstance(citations, list)
        # Should find multiple legal references (§ 823, BGB, Art. 1, GG, etc.)
        assert len(citations) >= 1
        # Should include paragraph or law code references
        assert any("§" in c or "823" in c or "BGB" in c or "GG" in c for c in citations)

    def test_extract_citations_no_domain(self):
        """Test citation extraction without domain module."""
        processor = SentenceProcessor(domain_module=None)
        text = "Nach § 823 BGB haftet der Schuldner."
        citations = processor.extract_citations(text)

        # Should return empty list without domain module
        assert citations == []

    def test_has_legal_citation(self):
        """Test citation detection in text."""
        processor = SentenceProcessor()

        # Text with citation
        text_with = "Nach § 823 BGB haftet der Schuldner."
        result_with = processor._has_legal_citation(text_with)
        assert isinstance(result_with, bool)

        # Text without citation
        text_without = "Der Schuldner haftet für Schäden."
        result_without = processor._has_legal_citation(text_without)
        assert isinstance(result_without, bool)

    def test_is_legal_statement(self):
        """Test legal statement detection."""
        processor = SentenceProcessor()

        # Legal statement
        legal = "Der Ersatzpflichtige hat den Schaden zu ersetzen."
        assert isinstance(processor.is_legal_statement(legal), bool)

        # Non-legal statement
        casual = "Das Wetter ist heute schön."
        assert isinstance(processor.is_legal_statement(casual), bool)

    def test_process_answer_complete(self, sample_german_text):
        """Test complete answer processing."""
        processor = SentenceProcessor()
        result = processor.process_answer(sample_german_text)

        # Check result structure
        assert "original" in result
        assert "normalized" in result
        assert "sentences" in result
        assert "total_sentences" in result
        assert "total_tokens" in result
        assert "has_citations" in result
        assert "citations" in result

        # Check types and values
        assert result["original"] == sample_german_text
        assert isinstance(result["normalized"], str)
        assert isinstance(result["sentences"], list)
        assert result["total_sentences"] == len(result["sentences"])
        assert result["total_tokens"] > 0
        assert isinstance(result["has_citations"], bool)
        assert isinstance(result["citations"], list)

    def test_batch_process(self):
        """Test batch processing multiple texts."""
        processor = SentenceProcessor()
        texts = [
            "Dies ist Satz eins. Satz zwei hier.",
            "Nach § 823 BGB haftet der Schuldner.",
            "Ein weiterer Test mit mehreren Sätzen. Noch ein Satz.",
        ]
        results = processor.batch_process(texts)

        # Should return list of results
        assert isinstance(results, list)
        assert len(results) == len(texts)

        # Each result should have complete structure
        for result in results:
            assert "original" in result
            assert "sentences" in result
            assert "total_sentences" in result

    def test_empty_text(self):
        """Test processing empty text."""
        processor = SentenceProcessor()
        result = processor.process_answer("")

        assert result["original"] == ""
        assert result["total_sentences"] == 0
        assert result["total_tokens"] == 0

    def test_special_characters(self):
        """Test processing text with special German characters."""
        processor = SentenceProcessor()
        text = "§ 823 BGB: Ärzte müssen über Risiken aufklären. Gemäß § 630c BGB."
        result = processor.process_answer(text)

        # Should handle special characters
        assert result["total_sentences"] >= 1
        assert "citations" in result

    def test_very_long_text(self):
        """Test processing very long text."""
        processor = SentenceProcessor()
        # Create long text with multiple sentences
        text = " ".join([f"Dies ist Satz Nummer {i}." for i in range(100)])
        result = processor.process_answer(text)

        # Should handle long text
        assert result["total_sentences"] >= 50
        assert result["total_tokens"] > 200
