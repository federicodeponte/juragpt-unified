# -*- coding: utf-8 -*-
"""
Unit tests for StorageInterface module.

Note: Most StorageInterface tests require integration with VerificationService
because store_verification() expects a specific nested structure from the service.
Full end-to-end storage testing is done in integration tests.

These unit tests focus on:
- Initialization
- Session management
- Basic database operations
"""

import os
import pytest
from datetime import datetime
from auditor.storage.storage_interface import StorageInterface
from auditor.storage.database import VerificationLog


class TestStorageInterface:
    """Test StorageInterface basic functionality."""

    @pytest.fixture
    def storage(self, test_db_path):
        """Create storage interface with test database."""
        return StorageInterface(database_url=f"sqlite:///{test_db_path}")

    def test_initialization_default(self):
        """Test default initialization."""
        storage = StorageInterface()
        assert storage.database_url == "sqlite:///auditor.db"
        assert storage.SessionLocal is not None

    def test_initialization_with_custom_url(self, test_db_path):
        """Test initialization with custom database URL."""
        storage = StorageInterface(database_url=f"sqlite:///{test_db_path}")
        assert storage.database_url == f"sqlite:///{test_db_path}"
        assert storage.SessionLocal is not None

    def test_initialization_with_memory_db(self):
        """Test initialization with in-memory database."""
        storage = StorageInterface(database_url="sqlite:///:memory:")
        assert storage.database_url == "sqlite:///:memory:"

    def test_get_session(self, storage):
        """Test session creation."""
        session = storage._get_session()
        assert session is not None

        # Session should be usable
        assert session.is_active

        # Cleanup
        session.close()

    def test_multiple_sessions(self, storage):
        """Test creating multiple sessions."""
        session1 = storage._get_session()
        session2 = storage._get_session()

        # Should be different session objects
        assert session1 is not session2

        # Cleanup
        session1.close()
        session2.close()

    def test_database_tables_exist(self, storage):
        """Test that database tables are created."""
        session = storage._get_session()

        try:
            # Should be able to query VerificationLog table
            count = session.query(VerificationLog).count()
            assert count == 0  # No data yet
        finally:
            session.close()

    @pytest.mark.skipif(
        not os.getenv("POSTGRES_AVAILABLE"),
        reason="PostgreSQL server not running"
    )
    def test_postgresql_url_format(self):
        """Test PostgreSQL URL format."""
        pg_url = "postgresql://user:pass@localhost/auditor"
        storage = StorageInterface(database_url=pg_url)
        assert storage.database_url == pg_url

    # Note: store_verification(), get_verification(), and query methods
    # are tested in integration tests because they require the full
    # verification result structure from VerificationService.
