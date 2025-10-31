# -*- coding: utf-8 -*-
"""
Shared pytest fixtures for all test modules.
"""

import json
import os
import tempfile
from pathlib import Path
from typing import Dict, Any, List

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from auditor.storage.database import Base
from auditor.config.settings import Settings


# ==================== Paths and Data ====================


@pytest.fixture(scope="session")
def project_root() -> Path:
    """Get project root directory."""
    return Path(__file__).parent.parent


@pytest.fixture(scope="session")
def data_dir(project_root: Path) -> Path:
    """Get data directory with mock datasets."""
    return project_root / "data"


@pytest.fixture(scope="session")
def mock_laws(data_dir: Path) -> List[Dict[str, Any]]:
    """Load mock German laws."""
    with open(data_dir / "laws.json", "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def mock_cases(data_dir: Path) -> List[Dict[str, Any]]:
    """Load mock court cases."""
    with open(data_dir / "cases.json", "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def mock_queries(data_dir: Path) -> List[Dict[str, Any]]:
    """Load mock legal queries."""
    with open(data_dir / "mock_queries.json", "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def mock_answers(data_dir: Path) -> List[Dict[str, Any]]:
    """Load mock LLM answers."""
    with open(data_dir / "mock_answers.json", "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture(scope="session")
def edge_cases(data_dir: Path) -> List[Dict[str, Any]]:
    """Load edge case scenarios."""
    with open(data_dir / "edge_cases.json", "r", encoding="utf-8") as f:
        return json.load(f)


# ==================== Database ====================


@pytest.fixture(scope="function")
def test_db_path():
    """Create temporary database file."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    # Cleanup
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture(scope="function")
def test_engine(test_db_path: str):
    """Create test database engine."""
    engine = create_engine(f"sqlite:///{test_db_path}", echo=False)
    Base.metadata.create_all(engine)
    yield engine
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture(scope="function")
def test_session(test_engine) -> Session:
    """Create test database session."""
    SessionLocal = sessionmaker(bind=test_engine)
    session = SessionLocal()
    yield session
    session.close()


# ==================== Sample Data ====================


@pytest.fixture
def sample_german_text() -> str:
    """Sample German legal text."""
    return (
        "Nach § 823 Abs. 1 BGB haftet, wer vorsätzlich oder fahrlässig "
        "das Leben, den Körper, die Gesundheit, die Freiheit, das Eigentum "
        "oder ein sonstiges Recht eines anderen widerrechtlich verletzt. "
        "Der Ersatzpflichtige hat den Schaden zu ersetzen."
    )


@pytest.fixture
def sample_sources() -> List[Dict[str, Any]]:
    """Sample source documents for verification."""
    return [
        {
            "text": (
                "Wer vorsätzlich oder fahrlässig das Leben, den Körper, "
                "die Gesundheit, die Freiheit, das Eigentum oder ein sonstiges "
                "Recht eines anderen widerrechtlich verletzt, ist dem anderen "
                "zum Ersatz des daraus entstehenden Schadens verpflichtet."
            ),
            "source_id": "bgb_823_1",
            "score": 0.95,
            "extra_metadata": {"law": "BGB", "section": "§ 823 Abs. 1"},
        },
        {
            "text": (
                "Die gleiche Verpflichtung trifft denjenigen, welcher gegen "
                "ein den Schutz eines anderen bezweckendes Gesetz verstößt."
            ),
            "source_id": "bgb_823_2",
            "score": 0.85,
            "extra_metadata": {"law": "BGB", "section": "§ 823 Abs. 2"},
        },
    ]


@pytest.fixture
def sample_verification_request() -> Dict[str, Any]:
    """Sample verification request payload."""
    return {
        "answer": (
            "Nach § 823 BGB haftet, wer vorsätzlich oder fahrlässig "
            "einen Schaden verursacht."
        ),
        "sources": [
            {
                "text": (
                    "Wer vorsätzlich oder fahrlässig das Leben, den Körper, "
                    "die Gesundheit verletzt, haftet."
                ),
                "source_id": "bgb_823",
                "score": 0.90,
            }
        ],
        "threshold": 0.75,
        "auto_retry": True,
    }


# ==================== Settings ====================


@pytest.fixture(scope="function")
def test_settings(test_db_path: str) -> Settings:
    """Create test settings."""
    return Settings(
        database_url=f"sqlite:///{test_db_path}",
        embedding_model="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",  # Smaller for tests
        spacy_model="de_core_news_sm",  # Smaller for tests
        cache_enabled=False,  # Disable cache for predictable tests
        auto_retry=True,
        confidence_threshold=0.75,
    )


# ==================== Markers ====================


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')")
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "edge_case: marks tests as edge case tests")
    config.addinivalue_line("markers", "performance: marks tests as performance benchmarks")
