"""Initial database schema

Revision ID: 001
Revises:
Create Date: 2025-10-30 15:30:00.000000

This migration creates the initial database schema for JuraGPT Auditor:
- verification_log: Stores verification results for audit trail
- embedding_cache: Caches embeddings for performance optimization
- source_fingerprints: Stores source fingerprints for change detection
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Create initial database schema.

    Creates three tables:
    1. verification_log - Audit trail for all verifications
    2. embedding_cache - Performance optimization for embeddings
    3. source_fingerprints - Change detection for sources
    """

    # Create verification_log table
    op.create_table(
        'verification_log',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('verification_id', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),

        # Answer data
        sa.Column('answer_text', sa.Text(), nullable=False),
        sa.Column('answer_hash', sa.String(length=64), nullable=False),
        sa.Column('answer_sentences', sa.Integer(), nullable=True),
        sa.Column('has_citations', sa.Boolean(), nullable=True),
        sa.Column('citations', sa.JSON(), nullable=True),

        # Source data
        sa.Column('source_count', sa.Integer(), nullable=True),
        sa.Column('source_fingerprints', sa.JSON(), nullable=True),

        # Verification results
        sa.Column('verified_sentences', sa.Integer(), nullable=True),
        sa.Column('verification_rate', sa.Float(), nullable=True),
        sa.Column('confidence_score', sa.Float(), nullable=False),
        sa.Column('trust_label', sa.String(length=20), nullable=False),

        # Confidence components
        sa.Column('semantic_similarity', sa.Float(), nullable=True),
        sa.Column('retrieval_quality', sa.Float(), nullable=True),
        sa.Column('citation_presence', sa.Float(), nullable=True),
        sa.Column('coverage', sa.Float(), nullable=True),

        # Retry information
        sa.Column('retry_attempts', sa.Integer(), nullable=True),

        # Metadata
        sa.Column('extra_metadata', sa.JSON(), nullable=True),

        # Validity
        sa.Column('is_valid', sa.Boolean(), nullable=True),
        sa.Column('invalidated_at', sa.DateTime(), nullable=True),

        # Performance
        sa.Column('duration_ms', sa.Float(), nullable=True),

        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for verification_log
    op.create_index(
        'ix_verification_log_verification_id',
        'verification_log',
        ['verification_id'],
        unique=True
    )
    op.create_index(
        'ix_verification_log_confidence_score',
        'verification_log',
        ['confidence_score'],
        unique=False
    )
    op.create_index(
        'ix_verification_log_trust_label',
        'verification_log',
        ['trust_label'],
        unique=False
    )
    op.create_index(
        'ix_verification_log_is_valid',
        'verification_log',
        ['is_valid'],
        unique=False
    )

    # Create embedding_cache table
    op.create_table(
        'embedding_cache',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('text_hash', sa.String(length=64), nullable=False),

        # Embedding data
        sa.Column('embedding', sa.JSON(), nullable=False),
        sa.Column('embedding_dim', sa.Integer(), nullable=False),
        sa.Column('model_name', sa.String(length=100), nullable=False),

        # Metadata
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('last_accessed', sa.DateTime(), nullable=False),
        sa.Column('access_count', sa.Integer(), nullable=True),

        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for embedding_cache
    op.create_index(
        'ix_embedding_cache_text_hash',
        'embedding_cache',
        ['text_hash'],
        unique=True
    )

    # Create source_fingerprints table
    op.create_table(
        'source_fingerprints',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),

        # Source identification
        sa.Column('source_id', sa.String(length=100), nullable=False),
        sa.Column('source_hash', sa.String(length=64), nullable=False),

        # Source content
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('text_length', sa.Integer(), nullable=False),

        # Versioning
        sa.Column('version', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),

        # Metadata
        sa.Column('extra_metadata', sa.JSON(), nullable=True),

        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for source_fingerprints
    op.create_index(
        'ix_source_fingerprints_source_id',
        'source_fingerprints',
        ['source_id'],
        unique=False
    )
    op.create_index(
        'ix_source_fingerprints_source_hash',
        'source_fingerprints',
        ['source_hash'],
        unique=True
    )


def downgrade() -> None:
    """
    Drop all tables created in upgrade.

    WARNING: This will delete all data!
    """
    # Drop indexes first
    op.drop_index('ix_source_fingerprints_source_hash', table_name='source_fingerprints')
    op.drop_index('ix_source_fingerprints_source_id', table_name='source_fingerprints')
    op.drop_index('ix_embedding_cache_text_hash', table_name='embedding_cache')
    op.drop_index('ix_verification_log_is_valid', table_name='verification_log')
    op.drop_index('ix_verification_log_trust_label', table_name='verification_log')
    op.drop_index('ix_verification_log_confidence_score', table_name='verification_log')
    op.drop_index('ix_verification_log_verification_id', table_name='verification_log')

    # Drop tables
    op.drop_table('source_fingerprints')
    op.drop_table('embedding_cache')
    op.drop_table('verification_log')
