"""
ABOUTME: Database models and schema for persistent storage
ABOUTME: Uses SQLAlchemy with support for SQLite and PostgreSQL
"""

from datetime import datetime
from typing import Optional
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Float,
    Boolean,
    DateTime,
    Text,
    JSON,
)
from sqlalchemy.orm import DeclarativeBase, sessionmaker, Session


class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


class VerificationLog(Base):
    """
    Stores verification results for audit trail.
    """

    __tablename__ = "verification_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    verification_id = Column(String(36), unique=True, nullable=False, index=True)

    # Timestamp
    created_at = Column(DateTime, default=datetime.now, nullable=False)

    # Answer data
    answer_text = Column(Text, nullable=False)
    answer_hash = Column(String(64), nullable=False)
    answer_sentences = Column(Integer, default=0)
    has_citations = Column(Boolean, default=False)
    citations = Column(JSON, nullable=True)  # List of citations

    # Source data
    source_count = Column(Integer, default=0)
    source_fingerprints = Column(JSON, nullable=True)  # List of hashes

    # Verification results
    verified_sentences = Column(Integer, default=0)
    verification_rate = Column(Float, default=0.0)
    confidence_score = Column(Float, nullable=False, index=True)
    trust_label = Column(String(20), nullable=False, index=True)

    # Confidence components
    semantic_similarity = Column(Float, nullable=True)
    retrieval_quality = Column(Float, nullable=True)
    citation_presence = Column(Float, nullable=True)
    coverage = Column(Float, nullable=True)

    # Retry information
    retry_attempts = Column(Integer, default=0)

    # Metadata (renamed to avoid SQLAlchemy reserved word)
    extra_metadata = Column(JSON, nullable=True)

    # Validity (for invalidation when sources change)
    is_valid = Column(Boolean, default=True, index=True)
    invalidated_at = Column(DateTime, nullable=True)

    # Performance
    duration_ms = Column(Float, nullable=True)

    def __repr__(self) -> str:
        return f"<VerificationLog(id={self.verification_id}, confidence={self.confidence_score:.2f}, label={self.trust_label})>"


class EmbeddingCache(Base):
    """
    Cache for embeddings to improve performance.
    """

    __tablename__ = "embedding_cache"

    id = Column(Integer, primary_key=True, autoincrement=True)
    text_hash = Column(String(64), unique=True, nullable=False, index=True)

    # Embedding data
    embedding = Column(JSON, nullable=False)  # Stored as list
    embedding_dim = Column(Integer, nullable=False)
    model_name = Column(String(100), nullable=False)

    # Metadata
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    last_accessed = Column(DateTime, default=datetime.now, nullable=False)
    access_count = Column(Integer, default=0)

    def __repr__(self) -> str:
        return f"<EmbeddingCache(hash={self.text_hash[:8]}..., dim={self.embedding_dim})>"


class SourceFingerprint(Base):
    """
    Stores source document fingerprints for change detection.
    """

    __tablename__ = "source_fingerprints"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Source identification
    source_id = Column(String(100), nullable=False, index=True)
    source_hash = Column(String(64), unique=True, nullable=False, index=True)

    # Source content
    text = Column(Text, nullable=False)
    text_length = Column(Integer, nullable=False)

    # Versioning
    version = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    # Metadata (renamed to avoid SQLAlchemy reserved word)
    extra_metadata = Column(JSON, nullable=True)

    def __repr__(self) -> str:
        return f"<SourceFingerprint(id={self.source_id}, hash={self.source_hash[:8]}..., v={self.version})>"


def create_database(database_url: str, echo: bool = False) -> tuple[sessionmaker, any]:
    """
    Create database engine and session factory.

    Args:
        database_url: SQLAlchemy database URL
        echo: Whether to echo SQL statements

    Returns:
        Tuple of (SessionLocal, engine)
    """
    engine = create_engine(database_url, echo=echo)

    # Create all tables
    Base.metadata.create_all(bind=engine)

    # Create session factory
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    return SessionLocal, engine


def get_session(SessionLocal: sessionmaker) -> Session:
    """
    Get a database session.

    Usage:
        with get_session(SessionLocal) as session:
            # Use session
            pass
    """
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def init_database(database_url: str = "sqlite:///auditor.db") -> sessionmaker:
    """
    Initialize database with default settings.

    Args:
        database_url: Database connection string

    Returns:
        SessionLocal factory
    """
    SessionLocal, engine = create_database(database_url, echo=False)
    print(f"✓ Database initialized: {database_url}")
    return SessionLocal


def main() -> None:
    """Demo usage of database"""
    print("🗄️  Database Schema Demo\n")

    # Create SQLite database
    SessionLocal = init_database("sqlite:///demo_auditor.db")

    # Create session
    session = SessionLocal()

    try:
        # Create verification log
        log = VerificationLog(
            verification_id="test_ver_001",
            answer_text="Test answer about § 823 BGB",
            answer_hash="abc123...",
            answer_sentences=2,
            has_citations=True,
            citations=["§ 823 BGB"],
            source_count=2,
            source_fingerprints=["hash1", "hash2"],
            verified_sentences=2,
            verification_rate=1.0,
            confidence_score=0.89,
            trust_label="✅ Verified",
            semantic_similarity=0.91,
            retrieval_quality=0.87,
            citation_presence=0.85,
            coverage=1.0,
            duration_ms=234.5,
        )

        session.add(log)
        session.commit()

        print(f"✓ Created: {log}")

        # Query
        result = session.query(VerificationLog).filter(
            VerificationLog.confidence_score > 0.8
        ).first()

        print(f"\n📊 Query Result:")
        print(f"   ID: {result.verification_id}")
        print(f"   Confidence: {result.confidence_score}")
        print(f"   Label: {result.trust_label}")
        print(f"   Created: {result.created_at}")

        # Count
        total = session.query(VerificationLog).count()
        print(f"\n📈 Total Verifications: {total}")

    finally:
        session.close()

    print("\n✓ Database demo complete")


if __name__ == "__main__":
    main()
