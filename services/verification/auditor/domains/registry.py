"""
ABOUTME: Domain registry for pluggable vertical configurations
ABOUTME: Maps domain presets to (language_module, domain_module) tuples
"""

from typing import Dict, Tuple, Type, Optional

from auditor.languages.base import BaseLanguageModule
from auditor.languages.german import GermanLanguageModule
from auditor.languages.multilingual import MultilingualModule
from auditor.domains.base import BaseDomain
from auditor.domains.legal.german import GermanLegalDomain
from auditor.domains.generic import GenericDomain


# Domain Registry: Maps preset names to (LanguageModule, DomainModule) classes
DOMAIN_REGISTRY: Dict[str, Tuple[Type[BaseLanguageModule], Optional[Type[BaseDomain]]]] = {
    # Legal domains
    "legal.german": (GermanLanguageModule, GermanLegalDomain),
    "german_legal": (GermanLanguageModule, GermanLegalDomain),  # Alias

    # Generic domains (language-specific, no vertical)
    "generic.german": (GermanLanguageModule, GenericDomain),
    "generic": (MultilingualModule, GenericDomain),  # Language-agnostic

    # Default
    "default": (GermanLanguageModule, GermanLegalDomain),
}


def get_modules_for_preset(preset: str) -> Tuple[BaseLanguageModule, Optional[BaseDomain]]:
    """
    Get instantiated language and domain modules for a preset.

    Args:
        preset: Preset name (e.g., "legal.german", "generic.german")

    Returns:
        Tuple of (language_module instance, domain_module instance or None)

    Raises:
        KeyError: If preset not found in registry
    """
    if preset not in DOMAIN_REGISTRY:
        available = ", ".join(DOMAIN_REGISTRY.keys())
        raise KeyError(
            f"Unknown domain preset: '{preset}'. "
            f"Available presets: {available}"
        )

    language_class, domain_class = DOMAIN_REGISTRY[preset]

    language_module = language_class()
    domain_module = domain_class() if domain_class is not None else None

    return language_module, domain_module


def register_domain(
    preset_name: str,
    language_class: Type[BaseLanguageModule],
    domain_class: Optional[Type[BaseDomain]] = None,
) -> None:
    """
    Register a new domain preset.

    Allows users to add custom domains at runtime.

    Args:
        preset_name: Name for the preset (e.g., "medical.german")
        language_class: Language module class
        domain_class: Domain module class (optional)

    Example:
        register_domain(
            "medical.german",
            GermanLanguageModule,
            GermanMedicalDomain,
        )
    """
    DOMAIN_REGISTRY[preset_name] = (language_class, domain_class)


def list_presets() -> Dict[str, str]:
    """
    List all available domain presets with descriptions.

    Returns:
        Dict mapping preset names to descriptions
    """
    descriptions = {}

    for preset, (lang_class, domain_class) in DOMAIN_REGISTRY.items():
        lang_name = lang_class.__name__.replace("LanguageModule", "")
        domain_name = domain_class.__name__.replace("Domain", "") if domain_class else "Generic"
        descriptions[preset] = f"{lang_name} - {domain_name}"

    return descriptions
