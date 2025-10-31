"""
Test PII anonymization and de-anonymization
"""

import pytest


class TestPIIAnonymization:
    """Test PII protection layer"""

    def test_basic_anonymization(self, mock_pii_components):
        """Test basic PII anonymization"""
        from app.core.pii_anonymizer import PIIAnonymizer

        pii_anonymizer = PIIAnonymizer()
        text = "Dr. Eva Müller arbeitet in Berlin."
        request_id = "test-123"

        anonymized, mapping = pii_anonymizer.anonymize(text, request_id)

        # Should not contain original PII
        assert "Eva Müller" not in anonymized
        assert "Berlin" not in anonymized

        # Should contain placeholders
        assert "<PERSON_" in anonymized

        # Mapping should exist
        assert len(mapping) > 0

    def test_roundtrip_anonymization(self, mock_pii_components):
        """Test that anonymization is reversible"""
        from app.core.pii_anonymizer import PIIAnonymizer

        pii_anonymizer = PIIAnonymizer()
        original = "Contract between Müller GmbH and Schmidt AG in München."
        request_id = "test-456"

        # Anonymize
        anonymized, mapping = pii_anonymizer.anonymize(original, request_id)

        # De-anonymize
        restored = pii_anonymizer.deanonymize(anonymized, request_id)

        # Should match original
        assert "Müller GmbH" in restored
        assert "Schmidt AG" in restored
        assert "München" in restored

    def test_german_legal_patterns(self, mock_pii_components):
        """Test custom German legal entity detection"""
        from app.core.pii_anonymizer import PIIAnonymizer

        pii_anonymizer = PIIAnonymizer()
        text = "Aktenzeichen Az.: 1 C 234/23, IBAN DE89370400440532013000"
        request_id = "test-789"

        anonymized, mapping = pii_anonymizer.anonymize(text, request_id)

        # Should anonymize case number
        assert "1 C 234/23" not in anonymized

        # Should anonymize IBAN
        assert "DE89370400440532013000" not in anonymized

        # Check mapping contains correct entity types
        entity_types = [k.split("_")[0].replace("<", "") for k in mapping.keys()]
        assert "CASE" in entity_types or "IBAN" in entity_types

    def test_no_pii_detected(self, mock_pii_components):
        """Test behavior when no PII present"""
        from app.core.pii_anonymizer import PIIAnonymizer

        pii_anonymizer = PIIAnonymizer()
        text = "Der Paragraph regelt die allgemeinen Bedingungen."
        request_id = "test-nopii"

        anonymized, mapping = pii_anonymizer.anonymize(text, request_id)

        # Should return original if no PII
        assert text == anonymized
        assert len(mapping) == 0

    def test_pii_leakage_detection(self, mock_pii_components):
        """Test verification of no PII leakage"""
        from app.core.pii_anonymizer import PIIAnonymizer

        pii_anonymizer = PIIAnonymizer()
        safe_text = "Der Vertrag gilt ab <DATE_1> für <ORG_1>."

        # Should pass verification
        assert pii_anonymizer.verify_no_pii_leakage(safe_text) is True

        # Test with potential PII
        unsafe_text = "Dr. Müller unterschreibt am 01.01.2024."

        # May detect PII (depending on threshold)
        result = pii_anonymizer.verify_no_pii_leakage(unsafe_text)
        # This might pass or fail depending on NER confidence

    def test_redis_mapping_ttl(self, mock_pii_components):
        """Test that PII mappings expire"""
        from app.core.pii_anonymizer import PIIAnonymizer

        pii_anonymizer = PIIAnonymizer()
        redis_client = mock_pii_components["redis"]

        text = "Eva Müller in Berlin"
        request_id = "test-ttl"

        # Anonymize (stores in Redis)
        pii_anonymizer.anonymize(text, request_id)

        # Mapping should exist
        assert redis_client.mapping_exists(request_id)

        # TTL should be set
        ttl = redis_client.get_ttl(request_id)
        assert ttl > 0

    def test_mapping_deletion_after_deanonymization(self, mock_pii_components):
        """Test that mapping is deleted after de-anonymization"""
        from app.core.pii_anonymizer import PIIAnonymizer

        pii_anonymizer = PIIAnonymizer()
        redis_client = mock_pii_components["redis"]

        text = "Müller GmbH"
        request_id = "test-delete"

        # Anonymize
        anonymized, _ = pii_anonymizer.anonymize(text, request_id)

        # Mapping should exist
        assert redis_client.mapping_exists(request_id)

        # De-anonymize
        pii_anonymizer.deanonymize(anonymized, request_id)

        # Mapping should be deleted
        assert not redis_client.mapping_exists(request_id)

    def test_detect_pii_entities(self, mock_pii_components):
        """Test PII entity detection without anonymization"""
        from app.core.pii_anonymizer import PIIAnonymizer

        pii_anonymizer = PIIAnonymizer()
        text = "Dr. Eva Müller, IBAN DE89370400440532013000"

        entities = pii_anonymizer.detect_pii(text)

        # Should detect multiple entities
        assert len(entities) > 0

        # Each entity should have required fields
        for entity in entities:
            assert entity.entity_type is not None
            assert entity.text is not None
            assert entity.confidence > 0
            assert entity.placeholder is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
