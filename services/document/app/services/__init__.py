"""
ABOUTME: External service clients for third-party integrations
ABOUTME: Separated from core business logic for better SOLID architecture
"""

from app.services.modal_client import modal_ocr_client

__all__ = ["modal_ocr_client"]
