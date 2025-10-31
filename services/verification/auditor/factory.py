"""
ABOUTME: Service factory for creating pre-configured verification services
ABOUTME: Simplifies instantiation with domain presets
"""

from typing import Optional

from auditor.core.verification_service import VerificationService
from auditor.core.sentence_processor import SentenceProcessor
from auditor.core.semantic_matcher import SemanticMatcher
from auditor.core.confidence_engine import ConfidenceEngine
from auditor.core.fingerprint_tracker import FingerprintTracker
from auditor.config.settings import Settings
from auditor.domains.registry import get_modules_for_preset, list_presets


def create_verification_service(
    domain_preset: str = "default",
    settings: Optional[Settings] = None,
) -> VerificationService:
    """
    Create a pre-configured verification service for a domain.

    Args:
        domain_preset: Domain preset name (see list_domain_presets())
        settings: Optional settings (uses defaults if None)

    Returns:
        Configured VerificationService

    Example:
        # German legal (default)
        service = create_verification_service("legal.german")

        # Generic German (no domain-specific patterns)
        service = create_verification_service("generic.german")

    Raises:
        KeyError: If domain preset not found
    """
    # Get modules for preset
    language_module, domain_module = get_modules_for_preset(domain_preset)

    # Initialize settings if not provided
    if settings is None:
        settings = Settings()

    # Create sentence processor with modules
    sentence_processor = SentenceProcessor(
        language_module=language_module,
        domain_module=domain_module,
    )

    # Create other components
    semantic_matcher = SemanticMatcher(
        model_name=settings.embedding_model,
        device="cpu",
        cache_enabled=settings.enable_embedding_cache,
        cache_size=settings.max_cache_size,
    )

    confidence_engine = ConfidenceEngine(
        sentence_threshold=settings.sentence_threshold,
        overall_threshold=settings.overall_threshold,
    )

    fingerprint_tracker = FingerprintTracker(auto_invalidate=True)

    # Create verification service
    return VerificationService(
        settings=settings,
        sentence_processor=sentence_processor,
        semantic_matcher=semantic_matcher,
        confidence_engine=confidence_engine,
        fingerprint_tracker=fingerprint_tracker,
    )


def list_domain_presets() -> None:
    """
    Print all available domain presets.

    Usage:
        from auditor.factory import list_domain_presets
        list_domain_presets()
    """
    print("Available domain presets:")
    print()

    presets = list_presets()
    for preset, description in presets.items():
        print(f"  {preset:<20} - {description}")

    print()
    print("Usage:")
    print('  service = create_verification_service("legal.german")')
