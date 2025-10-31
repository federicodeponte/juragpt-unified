"""
ABOUTME: Custom exception hierarchy for JuraGPT RAG system.
ABOUTME: Provides type-safe, specific exceptions for better error handling and debugging.
"""

from typing import Optional, Any


class JuraGPTException(Exception):
    """
    Base exception for all JuraGPT errors.

    All custom exceptions inherit from this class, allowing
    catch-all error handling when needed.
    """

    def __init__(self, message: str, details: Optional[dict[str, Any]] = None):
        """
        Initialize exception with message and optional details.

        Args:
            message: Human-readable error description
            details: Optional dictionary with error context
        """
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        """Return formatted error message with details."""
        if self.details:
            details_str = ", ".join(f"{k}={v}" for k, v in self.details.items())
            return f"{self.message} ({details_str})"
        return self.message


# Data Fetching Errors
class DataFetchError(JuraGPTException):
    """Base exception for data fetching failures."""
    pass


class APIConnectionError(DataFetchError):
    """Failed to connect to external API."""

    def __init__(
        self,
        api_name: str,
        endpoint: str,
        reason: Optional[str] = None,
    ):
        message = f"Failed to connect to {api_name} API at {endpoint}"
        if reason:
            message += f": {reason}"
        super().__init__(message, {"api": api_name, "endpoint": endpoint})


class APIResponseError(DataFetchError):
    """API returned invalid or unexpected response."""

    def __init__(
        self,
        api_name: str,
        status_code: Optional[int] = None,
        response_body: Optional[str] = None,
    ):
        message = f"{api_name} API returned invalid response"
        if status_code:
            message += f" (status {status_code})"
        super().__init__(
            message,
            {"api": api_name, "status_code": status_code, "body": response_body},
        )


class RateLimitExceededError(DataFetchError):
    """API rate limit exceeded."""

    def __init__(self, api_name: str, retry_after: Optional[int] = None):
        message = f"{api_name} API rate limit exceeded"
        if retry_after:
            message += f", retry after {retry_after}s"
        super().__init__(message, {"api": api_name, "retry_after": retry_after})


# Data Validation Errors
class ValidationError(JuraGPTException):
    """Base exception for data validation failures."""
    pass


class DocumentValidationError(ValidationError):
    """Document failed validation checks."""

    def __init__(self, doc_id: str, reason: str):
        message = f"Document '{doc_id}' validation failed: {reason}"
        super().__init__(message, {"doc_id": doc_id, "reason": reason})


class MissingRequiredFieldError(ValidationError):
    """Required field missing from document."""

    def __init__(self, doc_id: str, field_name: str):
        message = f"Document '{doc_id}' missing required field: {field_name}"
        super().__init__(message, {"doc_id": doc_id, "field": field_name})


class InvalidFieldTypeError(ValidationError):
    """Field has incorrect type."""

    def __init__(self, doc_id: str, field_name: str, expected_type: str, actual_type: str):
        message = (
            f"Document '{doc_id}' field '{field_name}' has invalid type: "
            f"expected {expected_type}, got {actual_type}"
        )
        super().__init__(
            message,
            {
                "doc_id": doc_id,
                "field": field_name,
                "expected": expected_type,
                "actual": actual_type,
            },
        )


# Processing Errors
class ProcessingError(JuraGPTException):
    """Base exception for data processing failures."""
    pass


class NormalizationError(ProcessingError):
    """Text normalization failed."""

    def __init__(self, doc_id: str, reason: str):
        message = f"Failed to normalize document '{doc_id}': {reason}"
        super().__init__(message, {"doc_id": doc_id, "reason": reason})


class ChunkingError(ProcessingError):
    """Text chunking failed."""

    def __init__(self, doc_id: str, reason: str):
        message = f"Failed to chunk document '{doc_id}': {reason}"
        super().__init__(message, {"doc_id": doc_id, "reason": reason})


class EmbeddingError(ProcessingError):
    """Embedding generation failed."""

    def __init__(self, chunk_id: str, reason: str):
        message = f"Failed to generate embedding for chunk '{chunk_id}': {reason}"
        super().__init__(message, {"chunk_id": chunk_id, "reason": reason})


# Storage Errors
class StorageError(JuraGPTException):
    """Base exception for storage operations."""
    pass


class VectorDBConnectionError(StorageError):
    """Failed to connect to vector database."""

    def __init__(self, db_name: str, reason: Optional[str] = None):
        message = f"Failed to connect to {db_name}"
        if reason:
            message += f": {reason}"
        super().__init__(message, {"database": db_name})


class VectorDBWriteError(StorageError):
    """Failed to write to vector database."""

    def __init__(self, db_name: str, operation: str, reason: Optional[str] = None):
        message = f"Failed to {operation} in {db_name}"
        if reason:
            message += f": {reason}"
        super().__init__(message, {"database": db_name, "operation": operation})


class CollectionNotFoundError(StorageError):
    """Vector database collection does not exist."""

    def __init__(self, collection_name: str):
        message = f"Collection '{collection_name}' does not exist"
        super().__init__(message, {"collection": collection_name})


# Checkpoint/State Management Errors
class CheckpointError(JuraGPTException):
    """Base exception for checkpoint operations."""
    pass


class CheckpointLoadError(CheckpointError):
    """Failed to load checkpoint."""

    def __init__(self, checkpoint_path: str, reason: str):
        message = f"Failed to load checkpoint from '{checkpoint_path}': {reason}"
        super().__init__(message, {"path": checkpoint_path, "reason": reason})


class CheckpointSaveError(CheckpointError):
    """Failed to save checkpoint."""

    def __init__(self, checkpoint_path: str, reason: str):
        message = f"Failed to save checkpoint to '{checkpoint_path}': {reason}"
        super().__init__(message, {"path": checkpoint_path, "reason": reason})


class CheckpointCorruptedError(CheckpointError):
    """Checkpoint file is corrupted or invalid."""

    def __init__(self, checkpoint_path: str):
        message = f"Checkpoint file '{checkpoint_path}' is corrupted or invalid"
        super().__init__(message, {"path": checkpoint_path})


# Configuration Errors
class ConfigurationError(JuraGPTException):
    """Base exception for configuration issues."""
    pass


class MissingEnvironmentVariableError(ConfigurationError):
    """Required environment variable not set."""

    def __init__(self, var_name: str):
        message = f"Required environment variable '{var_name}' not set"
        super().__init__(message, {"variable": var_name})


class InvalidConfigurationError(ConfigurationError):
    """Configuration value is invalid."""

    def __init__(self, config_key: str, reason: str):
        message = f"Invalid configuration for '{config_key}': {reason}"
        super().__init__(message, {"config_key": config_key, "reason": reason})


# Pipeline Errors
class PipelineError(JuraGPTException):
    """Base exception for ETL pipeline failures."""
    pass


class PipelineStageError(PipelineError):
    """Specific pipeline stage failed."""

    def __init__(self, stage_name: str, reason: str):
        message = f"Pipeline stage '{stage_name}' failed: {reason}"
        super().__init__(message, {"stage": stage_name, "reason": reason})


class PipelineInterruptedError(PipelineError):
    """Pipeline was interrupted before completion."""

    def __init__(self, stage_name: str, checkpoint_path: Optional[str] = None):
        message = f"Pipeline interrupted at stage '{stage_name}'"
        details = {"stage": stage_name}
        if checkpoint_path:
            message += f", checkpoint saved to '{checkpoint_path}'"
            details["checkpoint"] = checkpoint_path
        super().__init__(message, details)
