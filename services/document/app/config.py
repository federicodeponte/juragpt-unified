"""
ABOUTME: Application configuration management using Pydantic settings
ABOUTME: Loads and validates environment variables for JuraGPT backend
"""

from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=False, extra="ignore"
    )

    # Supabase
    supabase_url: str
    supabase_key: str
    supabase_service_role_key: str

    # Gemini
    gemini_api_key: str
    gemini_model: str = "gemini-2.5-pro"
    gemini_temperature: float = 0.1
    gemini_endpoint: str = "https://generativelanguage.googleapis.com"
    # Use EU endpoint: https://europe-west8-generativelanguage.googleapis.com for GDPR compliance

    # Redis
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_password: str = ""
    redis_db: int = 0

    # Redis Connection Pool
    redis_max_connections: int = 50  # Maximum connections in pool
    redis_socket_timeout: int = 5  # Socket timeout in seconds
    redis_socket_connect_timeout: int = 5  # Connection timeout
    redis_socket_keepalive: bool = True  # Enable TCP keepalive
    redis_health_check_interval: int = 30  # Health check interval in seconds

    # Redis Caching
    cache_enabled: bool = True  # Enable query result caching
    cache_query_results_ttl: int = 3600  # 1 hour - retrieval results cache
    cache_documents_ttl: int = 7200  # 2 hours - document metadata cache
    cache_query_logs_ttl: int = 300  # 5 minutes - query history cache

    # Application
    environment: str = "development"
    log_level: str = "INFO"
    api_v1_prefix: str = "/api/v1"

    # Security
    secret_key: str
    allowed_origins: List[str] = ["http://localhost:3000"]

    # Models
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"

    # PII Protection
    pii_mapping_ttl: int = 300
    pii_confidence_threshold: float = 0.7

    # Retrieval
    default_top_k: int = 5
    max_chunk_size: int = 1000
    chunk_overlap: int = 100

    # Local Verification (Ollama)
    ollama_endpoint: str = "http://localhost:11434"
    ollama_model: str = "mistral:7b"
    use_local_verifier: bool = True

    # Data Retention (GDPR Compliance)
    chunks_retention_days: int = 730  # 2 years
    logs_retention_days: int = 90  # 90 days
    usage_retention_months: int = 13  # 13 months

    # Modal OCR Configuration
    modal_token_id: str = ""
    modal_token_secret: str = ""
    modal_app_name: str = "juragpt-ocr"
    modal_timeout: int = 300  # 5 minutes for GPU cold start + processing
    modal_enabled: bool = True
    enable_handwriting_ocr: bool = True

    # Sentry Error Tracking
    sentry_dsn: str = ""  # Empty string disables Sentry
    sentry_environment: str = ""  # Auto-detected from environment if not set
    sentry_traces_sample_rate: float = 0.1  # 10% performance monitoring
    sentry_profiles_sample_rate: float = 0.1  # 10% profiling


# Global settings instance
settings = Settings()
