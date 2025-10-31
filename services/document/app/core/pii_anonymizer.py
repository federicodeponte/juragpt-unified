"""
ABOUTME: PII anonymization layer for GDPR-compliant document processing
ABOUTME: Uses Presidio + custom German legal entity recognizers with Redis caching
"""

from typing import Dict, List, Tuple

from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig

from app.config import settings
from app.db.models import PIIEntity
from app.utils.logging import logger
from app.utils.redis_client import redis_client


class PIIAnonymizer:
    """
    GDPR-compliant PII anonymization for legal documents
    Supports German language with custom legal entity patterns
    """

    def __init__(self):
        # Initialize Presidio engines
        self.analyzer = self._setup_analyzer()
        self.anonymizer = AnonymizerEngine()

        # Entity type counters for unique placeholders
        self.entity_counters: Dict[str, int] = {}

    def _setup_analyzer(self) -> AnalyzerEngine:
        """
        Set up Presidio analyzer with German NLP and custom recognizers
        """
        # Configure NLP engine for German
        nlp_configuration = {
            "nlp_engine_name": "spacy",
            "models": [{"lang_code": "de", "model_name": "de_core_news_sm"}],
        }

        nlp_engine = NlpEngineProvider(nlp_conf=nlp_configuration).create_engine()

        # Create analyzer with German support
        analyzer = AnalyzerEngine(nlp_engine=nlp_engine, supported_languages=["de", "en"])

        # Add custom German legal recognizers
        self._add_custom_recognizers(analyzer)

        return analyzer

    def _add_custom_recognizers(self, analyzer: AnalyzerEngine):
        """Add custom pattern recognizers for German legal entities"""

        # German case numbers (e.g., "Az.: 1 C 234/23", "1 BvR 123/45")
        case_number_pattern = Pattern(
            name="german_case_number",
            regex=r"(?:Az\.|Aktenzeichen)?\s*\d+\s+[A-Z][a-z]?\s+\d+/\d+",
            score=0.85,
        )
        case_recognizer = PatternRecognizer(
            supported_entity="CASE_NUMBER",
            patterns=[case_number_pattern],
            context=["Gericht", "Urteil", "Beschluss"],
        )
        analyzer.registry.add_recognizer(case_recognizer)

        # German IBAN
        iban_pattern = Pattern(name="german_iban", regex=r"DE\d{2}\s?(\d{4}\s?){4}\d{2}", score=0.9)
        iban_recognizer = PatternRecognizer(supported_entity="IBAN", patterns=[iban_pattern])
        analyzer.registry.add_recognizer(iban_recognizer)

        # German VAT ID (Umsatzsteuer-ID)
        vat_pattern = Pattern(name="german_vat", regex=r"DE\d{9}", score=0.85)
        vat_recognizer = PatternRecognizer(
            supported_entity="VAT_ID",
            patterns=[vat_pattern],
            context=["USt", "Umsatzsteuer", "Steuer"],
        )
        analyzer.registry.add_recognizer(vat_recognizer)

        # Contract numbers
        contract_pattern = Pattern(
            name="contract_number",
            regex=r"(?:Vertrag|Vertrags-Nr\.|V-Nr\.)\s*[A-Z0-9\-/]+",
            score=0.75,
        )
        contract_recognizer = PatternRecognizer(
            supported_entity="CONTRACT_NUMBER", patterns=[contract_pattern]
        )
        analyzer.registry.add_recognizer(contract_recognizer)

    def anonymize(self, text: str, request_id: str) -> Tuple[str, Dict[str, str]]:
        """
        Anonymize PII in text and store mapping in Redis

        Args:
            text: Original text with PII
            request_id: Unique request identifier

        Returns:
            Tuple of (anonymized_text, mapping_dict)
        """
        # Reset entity counters for this request
        self.entity_counters = {}

        # Analyze text for PII
        analyzer_results = self.analyzer.analyze(
            text=text, language="de", score_threshold=settings.pii_confidence_threshold
        )

        if not analyzer_results:
            # No PII detected, return original text
            logger.info(f"No PII detected in request {request_id}")
            return text, {}

        # Create custom operators for each entity type
        operators = {}
        mapping = {}

        for result in analyzer_results:
            entity_type = result.entity_type
            original_text = text[result.start : result.end]

            # Generate unique placeholder
            placeholder = self._generate_placeholder(entity_type)

            # Store mapping
            mapping[placeholder] = original_text

            # Create operator for this specific instance
            operators[str(result)] = OperatorConfig("replace", {"new_value": placeholder})

        # Anonymize text
        anonymized_result = self.anonymizer.anonymize(
            text=text, analyzer_results=analyzer_results, operators=operators
        )

        # Store mapping in Redis
        redis_client.store_pii_mapping(request_id, mapping)

        logger.info(
            f"Anonymized {len(mapping)} PII entities",
            extra={"request_id": request_id, "entity_count": len(mapping)},
        )

        return anonymized_result.text, mapping

    def deanonymize(self, text: str, request_id: str) -> str:
        """
        Restore original PII from anonymized text

        Args:
            text: Anonymized text with placeholders
            request_id: Request identifier to fetch mapping

        Returns:
            Original text with PII restored
        """
        # Retrieve mapping from Redis
        mapping = redis_client.get_pii_mapping(request_id)

        if not mapping:
            logger.warning(f"No PII mapping found for request {request_id}")
            return text

        # Replace all placeholders with original values
        deanonymized_text = text
        for placeholder, original in mapping.items():
            deanonymized_text = deanonymized_text.replace(placeholder, original)

        # Delete mapping from Redis (one-time use)
        redis_client.delete_pii_mapping(request_id)

        logger.info(
            f"De-anonymized text for request {request_id}", extra={"request_id": request_id}
        )

        return deanonymized_text

    def _generate_placeholder(self, entity_type: str) -> str:
        """
        Generate unique placeholder for entity type
        Example: <PERSON_1>, <ORG_2>, <IBAN_1>
        """
        if entity_type not in self.entity_counters:
            self.entity_counters[entity_type] = 0

        self.entity_counters[entity_type] += 1
        count = self.entity_counters[entity_type]

        return f"<{entity_type}_{count}>"

    def detect_pii(self, text: str) -> List[PIIEntity]:
        """
        Detect PII without anonymizing (for analysis/reporting)

        Returns:
            List of detected PII entities with metadata
        """
        analyzer_results = self.analyzer.analyze(
            text=text, language="de", score_threshold=settings.pii_confidence_threshold
        )

        entities = []
        for result in analyzer_results:
            original_text = text[result.start : result.end]
            placeholder = self._generate_placeholder(result.entity_type)

            entity = PIIEntity(
                entity_type=result.entity_type,
                text=original_text,
                start=result.start,
                end=result.end,
                confidence=result.score,
                placeholder=placeholder,
            )
            entities.append(entity)

        return entities

    def verify_no_pii_leakage(self, text: str) -> bool:
        """
        Verify that anonymized text contains no PII
        Returns True if safe, False if PII detected
        """
        pii_entities = self.detect_pii(text)

        if pii_entities:
            logger.warning(
                f"PII leakage detected: {len(pii_entities)} entities found",
                extra={"entity_types": [e.entity_type for e in pii_entities]},
            )
            return False

        return True


# Global instance
pii_anonymizer = PIIAnonymizer()
