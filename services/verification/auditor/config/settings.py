"""
ABOUTME: Configuration management for JuraGPT Auditor
ABOUTME: Loads settings from ENV variables and config.yaml with ENV taking precedence
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class VerificationThresholds(BaseSettings):
    """Verification confidence thresholds"""

    sentence: float = Field(default=0.75, ge=0.0, le=1.0)
    overall: float = Field(default=0.80, ge=0.0, le=1.0)
    strict_mode_boost: float = Field(default=0.05, ge=0.0, le=0.2)


class AutoRetryConfig(BaseSettings):
    """Auto-retry configuration"""

    enabled: bool = True
    threshold: float = Field(default=0.60, ge=0.0, le=1.0)
    max_retries: int = Field(default=2, ge=0, le=5)


class TrustLabels(BaseSettings):
    """Trust label strings"""

    verified: str = "✅ Verified"
    review: str = "⚠️ Review"
    rejected: str = "🚫 Rejected"


class ConfidenceMapping(BaseSettings):
    """Confidence score to label mapping"""

    verified_min: float = Field(default=0.80, ge=0.0, le=1.0)
    review_min: float = Field(default=0.60, ge=0.0, le=1.0)


class EmbeddingModelConfig(BaseSettings):
    """Embedding model configuration"""

    name: str = "intfloat/multilingual-e5-large"
    dimension: int = 768
    batch_size: int = 32
    device: str = "cpu"


class NLPModelConfig(BaseSettings):
    """NLP model configuration"""

    name: str = "de_core_news_md"
    language: str = "de"


class ModelCacheConfig(BaseSettings):
    """Model cache configuration"""

    enabled: bool = True
    max_size: int = 1000
    cache_dir: str = "~/.cache/auditor"


class DatabaseConfig(BaseSettings):
    """Database configuration"""

    default_url: str = "sqlite:///auditor.db"
    echo: bool = False
    pool_size: int = 5
    max_overflow: int = 10


class APIConfig(BaseSettings):
    """API server configuration"""

    host: str = "0.0.0.0"
    port: int = 8000
    reload: bool = False
    workers: int = 1


class CORSConfig(BaseSettings):
    """CORS configuration"""

    enabled: bool = True
    allow_origins: List[str] = ["*"]
    allow_methods: List[str] = ["GET", "POST"]
    allow_headers: List[str] = ["*"]


class MonitoringConfig(BaseSettings):
    """Monitoring configuration"""

    log_level: str = "INFO"
    log_format: str = "json"
    metrics_enabled: bool = True
    metrics_port: int = 9090
    prometheus_namespace: str = "auditor"
    prometheus_subsystem: str = "verification"


class FingerprintConfig(BaseSettings):
    """Fingerprinting configuration"""

    algorithm: str = "sha256"
    truncate_length: int = 16
    auto_invalidate_on_source_change: bool = True
    keep_history: bool = True


class PerformanceConfig(BaseSettings):
    """Performance limits and settings"""

    max_answer_length: int = 10000
    max_sources: int = 20
    timeout_seconds: int = 30
    parallel_processing_enabled: bool = False
    max_workers: int = 4


class Settings(BaseSettings):
    """
    Main settings class that combines all configuration sources.
    Priority: ENV variables > config.yaml > defaults
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Core settings from ENV
    sentence_threshold: float = Field(default=0.75, ge=0.0, le=1.0)
    overall_threshold: float = Field(default=0.80, ge=0.0, le=1.0)
    strict_mode: bool = False

    database_url: str = "sqlite:///auditor.db"

    model_cache_dir: str = "~/.cache/auditor"
    embedding_model: str = "intfloat/multilingual-e5-large"
    spacy_model: str = "de_core_news_md"

    # Domain configuration (new modular architecture)
    domain_preset: str = "default"  # legal.german, generic.german, etc.

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_reload: bool = False
    log_level: str = "INFO"

    enable_embedding_cache: bool = True
    max_cache_size: int = 1000

    enable_metrics: bool = True
    metrics_port: int = 9090

    auto_retry_enabled: bool = True
    auto_retry_threshold: float = Field(default=0.60, ge=0.0, le=1.0)
    max_retries: int = 2

    # Security configuration
    enable_auth: bool = False
    jwt_secret_key: str = "your-secret-key-change-in-production-min-32-chars"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30

    enable_rate_limiting: bool = False
    rate_limit_per_minute: int = 60
    rate_limit_burst: int = 10

    # CORS configuration
    cors_origins: Optional[str] = None  # Comma-separated
    cors_methods: str = "GET,POST"
    cors_headers: str = "Content-Type,Authorization,X-API-Key"
    cors_allow_credentials: bool = True

    # Environment
    environment: str = "development"  # development, staging, production

    # Nested configuration from YAML
    _yaml_config: Optional[Dict[str, Any]] = None

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)
        self._load_yaml_config()
        self._apply_strict_mode()

    def _load_yaml_config(self) -> None:
        """Load configuration from config.yaml if it exists"""
        config_path = Path("config.yaml")
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                self._yaml_config = yaml.safe_load(f)

    def _apply_strict_mode(self) -> None:
        """Apply strict mode threshold boost if enabled"""
        if self.strict_mode:
            boost = 0.05
            if self._yaml_config:
                boost = (
                    self._yaml_config.get("verification", {})
                    .get("thresholds", {})
                    .get("strict_mode_boost", 0.05)
                )

            self.sentence_threshold = min(1.0, self.sentence_threshold + boost)
            self.overall_threshold = min(1.0, self.overall_threshold + boost)

    def get_verification_config(self) -> Dict[str, Any]:
        """Get verification-specific configuration"""
        return {
            "sentence_threshold": self.sentence_threshold,
            "overall_threshold": self.overall_threshold,
            "strict_mode": self.strict_mode,
            "auto_retry_enabled": self.auto_retry_enabled,
            "auto_retry_threshold": self.auto_retry_threshold,
            "max_retries": self.max_retries,
        }

    def get_model_config(self) -> Dict[str, Any]:
        """Get model-specific configuration"""
        return {
            "embedding_model": self.embedding_model,
            "spacy_model": self.spacy_model,
            "cache_dir": Path(self.model_cache_dir).expanduser(),
            "enable_cache": self.enable_embedding_cache,
            "max_cache_size": self.max_cache_size,
        }

    def get_database_config(self) -> Dict[str, Any]:
        """Get database configuration"""
        return {
            "url": self.database_url,
            "echo": False,
        }

    def get_trust_label(self, confidence: float) -> str:
        """Get trust label for a given confidence score"""
        verified_min = 0.80
        review_min = 0.60

        if self._yaml_config:
            mapping = self._yaml_config.get("verification", {}).get("confidence_mapping", {})
            verified_min = mapping.get("verified_min", 0.80)
            review_min = mapping.get("review_min", 0.60)

        if confidence >= verified_min:
            return "✅ Verified"
        elif confidence >= review_min:
            return "⚠️ Review"
        else:
            return "🚫 Rejected"


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Dependency injection helper for FastAPI"""
    return settings
