# Database Migrations

Database migration management for JuraGPT Auditor using Alembic.

## Quick Start

```bash
# Install migration dependencies
pip install -e ".[migrations]"

# Run migrations
alembic upgrade head

# Check current version
alembic current

# View migration history
alembic history --verbose
```

## Setup

### Initial Setup

The migration environment is already configured. To initialize migrations for the first time:

```bash
# Set DATABASE_URL environment variable
export DATABASE_URL=postgresql://user:password@localhost:5432/auditor

# Run all migrations
alembic upgrade head
```

### Configuration

**Alembic Configuration**: `alembic.ini`
- Migration scripts location: `alembic/`
- Version files: `alembic/versions/`
- Database URL: Uses `DATABASE_URL` environment variable (overrides alembic.ini)

**Environment Configuration**: `alembic/env.py`
- Automatically loads database models
- Uses settings from `auditor.config.settings`
- Supports offline and online migration modes

## Commands

### Viewing Migrations

```bash
# Show current database version
alembic current

# Show migration history
alembic history

# Show verbose history with details
alembic history --verbose

# Show pending migrations
alembic history --indicate-current
```

### Running Migrations

```bash
# Upgrade to latest version
alembic upgrade head

# Upgrade one version
alembic upgrade +1

# Upgrade to specific version
alembic upgrade 001

# Downgrade one version
alembic downgrade -1

# Downgrade to specific version
alembic downgrade 001

# Downgrade all (WARNING: destroys data!)
alembic downgrade base
```

### Creating Migrations

```bash
# Create empty migration
alembic revision -m "add_new_column"

# Auto-generate migration from model changes
alembic revision --autogenerate -m "add_user_table"

# Create migration with specific revision ID
alembic revision -m "add_index" --rev-id 002
```

**Note**: Always review auto-generated migrations before running!

### Testing Migrations

```bash
# Test upgrade
alembic upgrade head

# Test downgrade
alembic downgrade -1

# Test full cycle
alembic upgrade head
alembic downgrade base
alembic upgrade head
```

## Migration Files

### Initial Schema (001)

**File**: `alembic/versions/20251030_1530_initial_schema.py`
**Revision**: 001
**Created**: 2025-10-30

Creates initial database schema:

1. **verification_log**: Stores verification results
   - Columns: 25 (verification data, confidence scores, metadata)
   - Indexes: 4 (verification_id, confidence_score, trust_label, is_valid)

2. **embedding_cache**: Caches embeddings for performance
   - Columns: 7 (embeddings, model info, access tracking)
   - Indexes: 1 (text_hash)

3. **source_fingerprints**: Tracks source document changes
   - Columns: 9 (source identification, versioning, metadata)
   - Indexes: 2 (source_id, source_hash)

**Upgrade**: Creates all tables and indexes
**Downgrade**: Drops all tables (WARNING: destroys data!)

## Database Schema

### Tables

#### verification_log

Stores audit trail for all verifications.

| Column | Type | Description |
|--------|------|-------------|
| id | Integer | Primary key |
| verification_id | String(36) | UUID, unique, indexed |
| created_at | DateTime | Timestamp |
| answer_text | Text | Original answer |
| answer_hash | String(64) | SHA-256 hash |
| answer_sentences | Integer | Sentence count |
| has_citations | Boolean | Citation presence |
| citations | JSON | List of citations |
| source_count | Integer | Number of sources |
| source_fingerprints | JSON | Source hashes |
| verified_sentences | Integer | Verified sentence count |
| verification_rate | Float | Verification rate |
| confidence_score | Float | Overall confidence (indexed) |
| trust_label | String(20) | Trust label (indexed) |
| semantic_similarity | Float | Semantic component |
| retrieval_quality | Float | Retrieval component |
| citation_presence | Float | Citation component |
| coverage | Float | Coverage component |
| retry_attempts | Integer | Retry count |
| extra_metadata | JSON | Additional metadata |
| is_valid | Boolean | Validity flag (indexed) |
| invalidated_at | DateTime | Invalidation timestamp |
| duration_ms | Float | Processing time |

#### embedding_cache

Caches embeddings for performance optimization.

| Column | Type | Description |
|--------|------|-------------|
| id | Integer | Primary key |
| text_hash | String(64) | SHA-256 hash, unique, indexed |
| embedding | JSON | Embedding vector (list) |
| embedding_dim | Integer | Vector dimensions |
| model_name | String(100) | Model identifier |
| created_at | DateTime | Creation timestamp |
| last_accessed | DateTime | Last access time |
| access_count | Integer | Access counter |

#### source_fingerprints

Stores source fingerprints for change detection.

| Column | Type | Description |
|--------|------|-------------|
| id | Integer | Primary key |
| source_id | String(100) | Source identifier (indexed) |
| source_hash | String(64) | SHA-256 hash, unique, indexed |
| text | Text | Source text content |
| text_length | Integer | Text length |
| version | Integer | Version number |
| created_at | DateTime | Creation timestamp |
| updated_at | DateTime | Update timestamp |
| extra_metadata | JSON | Additional metadata |

## Migration Best Practices

### Before Creating Migrations

1. **Update models** in `auditor/storage/database.py`
2. **Review changes** carefully
3. **Test locally** before production
4. **Backup database** before running

### Creating Migrations

1. **Use descriptive names**:
   ```bash
   alembic revision -m "add_user_authentication"
   ```

2. **Review auto-generated migrations**:
   - Check column types
   - Verify indexes
   - Confirm constraints

3. **Add data migrations when needed**:
   ```python
   def upgrade():
       # Schema changes
       op.add_column('users', sa.Column('email', sa.String(255)))

       # Data migration
       conn = op.get_bind()
       conn.execute("UPDATE users SET email = username || '@example.com'")
   ```

4. **Always test downgrade**:
   ```bash
   alembic upgrade head
   alembic downgrade -1
   alembic upgrade head
   ```

### Running Migrations

1. **Backup database first**:
   ```bash
   pg_dump -h localhost -U auditor -d auditor > backup.sql
   ```

2. **Check current version**:
   ```bash
   alembic current
   ```

3. **Review pending migrations**:
   ```bash
   alembic history --indicate-current
   ```

4. **Run migrations**:
   ```bash
   alembic upgrade head
   ```

5. **Verify schema**:
   ```bash
   psql -h localhost -U auditor -d auditor -c "\d+"
   ```

## Production Deployment

### Pre-deployment Checklist

- [ ] Test migration on staging environment
- [ ] Backup production database
- [ ] Review migration SQL (use `--sql` flag)
- [ ] Schedule maintenance window
- [ ] Notify stakeholders

### Deployment Steps

1. **Backup database**:
   ```bash
   pg_dump -h prod-db -U auditor auditor > backup_$(date +%Y%m%d_%H%M%S).sql
   ```

2. **Generate SQL (optional)**:
   ```bash
   alembic upgrade head --sql > migration.sql
   # Review migration.sql before running
   ```

3. **Run migrations**:
   ```bash
   # With DATABASE_URL environment variable
   export DATABASE_URL=postgresql://user:pass@prod-db:5432/auditor
   alembic upgrade head
   ```

4. **Verify**:
   ```bash
   alembic current
   # Should show latest revision
   ```

5. **Restart application**:
   ```bash
   docker-compose restart auditor-api
   ```

### Rollback Procedure

If migration fails:

```bash
# Restore database from backup
psql -h prod-db -U auditor auditor < backup_20251030_123456.sql

# Or downgrade migration
alembic downgrade -1
```

## Troubleshooting

### Common Issues

**Issue**: `FAILED: Target database is not up to date.`
```bash
# Check current version
alembic current

# View history
alembic history

# Force stamp (use with caution!)
alembic stamp head
```

**Issue**: `Can't locate revision identified by 'xyz'`
```bash
# Verify migration files exist
ls alembic/versions/

# Check alembic_version table
psql -c "SELECT * FROM alembic_version;"
```

**Issue**: `Database URL not set`
```bash
# Set DATABASE_URL environment variable
export DATABASE_URL=postgresql://user:password@localhost:5432/auditor

# Or edit alembic.ini (not recommended for production)
```

**Issue**: Migration fails midway
```bash
# Check database state
alembic current

# Review partial changes
psql -c "\d+ tablename"

# Manually fix and stamp
# Fix database manually, then:
alembic stamp head
```

### Migration Conflicts

If you have conflicting migrations (multiple heads):

```bash
# View branches
alembic branches

# Merge branches
alembic merge -m "merge_branches" head1 head2
```

## Development Workflow

### Local Development

```bash
# 1. Make model changes in auditor/storage/database.py

# 2. Generate migration
alembic revision --autogenerate -m "add_column"

# 3. Review and edit migration file
vim alembic/versions/20251030_1600_add_column.py

# 4. Test migration
alembic upgrade head

# 5. Test rollback
alembic downgrade -1

# 6. Re-apply
alembic upgrade head

# 7. Commit migration file
git add alembic/versions/20251030_1600_add_column.py
git commit -m "Add column to users table"
```

### CI/CD Integration

Add to your CI pipeline:

```yaml
# .github/workflows/test.yml
- name: Run Migrations
  run: |
    export DATABASE_URL=postgresql://test:test@localhost:5432/test_db
    alembic upgrade head

- name: Test Application
  run: pytest
```

## See Also

- [Alembic Documentation](https://alembic.sqlalchemy.org/)
- [Database Configuration](../docs/CONFIGURATION.md#database-configuration)
- [Deployment Guide](../docs/DEPLOYMENT.md)
- [Storage Interface](../src/auditor/storage/README.md)
