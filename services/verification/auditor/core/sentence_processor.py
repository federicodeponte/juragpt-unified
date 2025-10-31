# -*- coding: utf-8 -*-
"""
ABOUTME: Sentence splitting and text normalization using pluggable language and domain modules
ABOUTME: Uses spaCy for accurate sentence boundary detection with domain-specific patterns
"""

import re
import warnings
from typing import List, Dict, Any, Optional
import spacy
from spacy.language import Language

from auditor.languages.base import BaseLanguageModule
from auditor.domains.base import BaseDomain

# Sentinel value to distinguish "not provided" from "explicitly None"
_NOT_PROVIDED = object()


class SentenceProcessor:
    """
    Modular sentence processor using pluggable language and domain modules.

    Supports:
    - Language modules (German, English, etc.)
    - Domain modules (Legal, Medical, etc.)
    - Backwards compatibility with old API

    New API (recommended):
        processor = SentenceProcessor(
            language_module=GermanLanguageModule(),
            domain_module=GermanLegalDomain(),
        )

    Old API (deprecated, auto-converts to German Legal):
        processor = SentenceProcessor(model_name="de_core_news_md")
    """

    def __init__(
        self,
        language_module: Optional[BaseLanguageModule] = None,
        domain_module: Optional[BaseDomain] = _NOT_PROVIDED,
        model_name: Optional[str] = None,  # Deprecated
    ):
        """
        Initialize sentence processor.

        Args:
            language_module: Language module (e.g., GermanLanguageModule)
            domain_module: Domain module (e.g., GermanLegalDomain)
                          If not provided, defaults to GermanLegalDomain.
                          Pass None explicitly to disable domain features.
            model_name: DEPRECATED - Use language_module instead
        """
        # Handle backwards compatibility
        if model_name is not None:
            warnings.warn(
                "model_name parameter is deprecated. Use language_module instead. "
                "Defaulting to GermanLanguageModule + GermanLegalDomain.",
                DeprecationWarning,
                stacklevel=2,
            )
            # Auto-convert to German Legal modules
            if language_module is None:
                from auditor.languages.german import GermanLanguageModule
                language_module = GermanLanguageModule()
            if domain_module is _NOT_PROVIDED:
                from auditor.domains.legal.german import GermanLegalDomain
                domain_module = GermanLegalDomain()

        # Set defaults if still None
        if language_module is None:
            from auditor.languages.german import GermanLanguageModule
            language_module = GermanLanguageModule()

        # Default to German Legal domain if not provided (but respect explicit None)
        if domain_module is _NOT_PROVIDED:
            from auditor.domains.legal.german import GermanLegalDomain
            domain_module = GermanLegalDomain()

        self.language_module = language_module
        self.domain_module = domain_module

        # Get model name from language module
        self.model_name = self.language_module.get_spacy_model()
        self._nlp: Optional[Language] = None

    @property
    def nlp(self) -> Optional[Language]:
        """
        Lazy load spaCy model.

        Returns None if no model specified (empty string from MultilingualModule).
        Allows fallback to basic sentence splitting.
        """
        if self._nlp is None and self.model_name:  # Only load if model_name is not empty
            try:
                self._nlp = spacy.load(self.model_name)
            except OSError:
                raise RuntimeError(
                    f"spaCy model '{self.model_name}' not found. "
                    f"Install it with: python -m spacy download {self.model_name}"
                )
        return self._nlp

    def normalize_text(self, text: str) -> str:
        """
        Normalize text using language module.

        Args:
            text: Raw text

        Returns:
            Normalized text
        """
        # Delegate to language module
        normalized = self.language_module.normalize_text(text)

        # Apply abbreviation expansions
        abbrev_map = self.language_module.get_abbreviation_mappings()
        for abbrev, expansion in abbrev_map.items():
            normalized = normalized.replace(abbrev, expansion)

        return normalized

    def split_sentences(self, text: str, min_length: int = 3) -> List[str]:
        """
        Split text into sentences using spaCy or basic fallback.

        Args:
            text: Input text
            min_length: Minimum sentence length in characters

        Returns:
            List of sentence strings
        """
        normalized = self.normalize_text(text)

        # Use spaCy if available, otherwise use basic splitting
        if self.nlp is not None:
            doc = self.nlp(normalized)
            sentences = [
                sent.text.strip()
                for sent in doc.sents
                if len(sent.text.strip()) >= min_length
            ]
        else:
            # Fallback: basic sentence splitting
            sentences = self.language_module.split_sentences_basic(normalized, min_length)

        return sentences

    def split_with_metadata(self, text: str) -> List[Dict[str, Any]]:
        """
        Split text into sentences with metadata.

        Returns:
            List of dicts with:
                - text: sentence text
                - start: character start position
                - end: character end position
                - index: sentence index
                - tokens: number of tokens
        """
        normalized = self.normalize_text(text)

        sentences = []

        # Use spaCy if available
        if self.nlp is not None:
            doc = self.nlp(normalized)
            for idx, sent in enumerate(doc.sents):
                if len(sent.text.strip()) < 3:
                    continue

                sentences.append({
                    "text": sent.text.strip(),
                    "start": sent.start_char,
                    "end": sent.end_char,
                    "index": idx,
                    "tokens": len(sent),
                    "has_citation": self._has_legal_citation(sent.text),
                })
        else:
            # Fallback: basic splitting without detailed metadata
            basic_sents = self.language_module.split_sentences_basic(normalized, min_length=3)
            pos = 0
            for idx, sent_text in enumerate(basic_sents):
                start = normalized.find(sent_text, pos)
                end = start + len(sent_text)
                pos = end

                # Estimate tokens (rough approximation)
                tokens = len(sent_text.split())

                sentences.append({
                    "text": sent_text,
                    "start": start if start >= 0 else idx * 100,
                    "end": end if start >= 0 else (idx + 1) * 100,
                    "index": idx,
                    "tokens": tokens,
                    "has_citation": self._has_legal_citation(sent_text),
                })

        return sentences

    def _has_legal_citation(self, text: str) -> bool:
        """
        Check if text contains domain citations.

        Delegates to domain module if available.

        Args:
            text: Input text

        Returns:
            True if citations found
        """
        if self.domain_module is None:
            return False

        citations = self.domain_module.extract_citations(text)
        return len(citations) > 0

    def extract_citations(self, text: str) -> List[str]:
        """
        Extract domain citations from text.

        Delegates to domain module if available.

        Args:
            text: Input text

        Returns:
            List of found citations (e.g., ["§ 823 BGB", "Art. 1 GG"])
        """
        if self.domain_module is None:
            return []

        return self.domain_module.extract_citations(text)

    def is_legal_statement(self, sentence: str) -> bool:
        """
        Determine if a sentence is a domain statement.

        Delegates to domain module if available.
        Kept name for backwards compatibility.

        Args:
            sentence: Sentence text

        Returns:
            True if sentence appears to be domain-specific
        """
        if self.domain_module is None:
            return False

        return self.domain_module.is_domain_statement(sentence)

    def process_answer(self, answer: str) -> Dict[str, Any]:
        """
        Process a complete answer into sentences with analysis.

        Args:
            answer: Full answer text

        Returns:
            Dict with:
                - original: original text
                - normalized: normalized text
                - sentences: list of sentence dicts
                - total_sentences: count
                - total_tokens: total token count
                - has_citations: whether answer contains citations
                - citations: list of found citations
        """
        normalized = self.normalize_text(answer)
        sentences = self.split_with_metadata(answer)
        citations = self.extract_citations(answer)

        return {
            "original": answer,
            "normalized": normalized,
            "sentences": sentences,
            "total_sentences": len(sentences),
            "total_tokens": sum(s["tokens"] for s in sentences),
            "has_citations": len(citations) > 0,
            "citations": citations,
        }

    def batch_process(self, texts: List[str]) -> List[Dict[str, Any]]:
        """
        Process multiple texts in batch.

        Args:
            texts: List of text strings

        Returns:
            List of processed results
        """
        return [self.process_answer(text) for text in texts]


def main() -> None:
    # Demo usage of sentence processor
    processor = SentenceProcessor()
    test_text = "Dies ist Satz eins. Dies ist Satz zwei mit BGB Bezug. Dritter Satz hier."
    print("Sentence Processor Demo")
    print("Original:", test_text[:50])
    result = processor.process_answer(test_text)
    print(f"Sentences: {result['total_sentences']}")
    print(f"Citations: {result['citations']}")
    for sent in result["sentences"]:
        print(f"  [{sent['index']}] {sent['text'][:40]}...")


if __name__ == "__main__":
    main()
