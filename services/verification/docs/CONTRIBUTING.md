# Contributing to JuraGPT Auditor

Thank you for your interest in contributing to JuraGPT Auditor! This document provides guidelines and instructions for contributing to the project.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Environment Setup](#development-environment-setup)
- [Project Structure](#project-structure)
- [Code Style Guidelines](#code-style-guidelines)
- [Testing Requirements](#testing-requirements)
- [Git Workflow](#git-workflow)
- [Pull Request Process](#pull-request-process)
- [Code Review Checklist](#code-review-checklist)
- [Reporting Bugs](#reporting-bugs)
- [Requesting Features](#requesting-features)
- [Community Guidelines](#community-guidelines)
- [Development Best Practices](#development-best-practices)

## Code of Conduct

We are committed to providing a welcoming and inclusive environment for all contributors. Please be respectful, constructive, and professional in all interactions.

### Our Standards

- **Be respectful**: Treat all contributors with respect and dignity
- **Be constructive**: Provide helpful feedback and suggestions
- **Be collaborative**: Work together to improve the project
- **Be professional**: Maintain a professional tone in all communications

### Unacceptable Behavior

- Harassment, discrimination, or offensive language
- Personal attacks or insults
- Spam or promotional content
- Violation of privacy or confidentiality

## Getting Started

### Prerequisites

Before contributing, ensure you have:

- **Python 3.11+** installed
- **Git** for version control
- **Docker** (optional, for containerized development)
- **PostgreSQL 15+** (if running locally without Docker)
- Basic knowledge of FastAPI, spaCy, and sentence-transformers

### Quick Start

```bash
# 1. Fork the repository on GitHub

# 2. Clone your fork
git clone https://github.com/YOUR_USERNAME/juragpt-auditor.git
cd juragpt-auditor

# 3. Add upstream remote
git remote add upstream https://github.com/ORIGINAL_OWNER/juragpt-auditor.git

# 4. Create a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 5. Install dependencies
pip install -e ".[dev]"

# 6. Download NLP models (this may take a few minutes)
python -m spacy download de_core_news_lg
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('paraphrase-multilingual-mpnet-base-v2')"

# 7. Set up environment variables
cp .env.example .env
# Edit .env with your database URL and other settings

# 8. Initialize the database
python -m auditor.storage.init_db

# 9. Run tests to verify setup
pytest

# 10. Start the development server
uvicorn auditor.api.server:app --reload --port 8000
```

Visit http://localhost:8000/docs to see the API documentation.

## Development Environment Setup

### Option 1: Local Development

**1. Install Python Dependencies**

```bash
# Install in editable mode with development extras
pip install -e ".[dev]"

# This installs:
# - Core dependencies (FastAPI, spaCy, sentence-transformers, etc.)
# - Development tools (pytest, black, ruff, mypy)
# - Database dependencies (SQLAlchemy, psycopg2)
```

**2. Download NLP Models**

The application requires two NLP models:

```bash
# German language model for spaCy (~500MB)
python -m spacy download de_core_news_lg

# Sentence transformer model for embeddings (~400MB)
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('paraphrase-multilingual-mpnet-base-v2')"
```

**3. Set Up PostgreSQL Database**

```bash
# Option A: Using Docker
docker run --name auditor-postgres \
  -e POSTGRES_USER=auditor \
  -e POSTGRES_PASSWORD=auditor_password \
  -e POSTGRES_DB=auditor \
  -p 5432:5432 \
  -d postgres:15

# Option B: Using existing PostgreSQL installation
createdb auditor
```

**4. Configure Environment Variables**

Create a `.env` file in the project root:

```bash
# Database
DATABASE_URL=postgresql://auditor:auditor_password@localhost:5432/auditor

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
LOG_LEVEL=DEBUG

# NLP Models
SPACY_MODEL=de_core_news_lg
EMBEDDING_MODEL=paraphrase-multilingual-mpnet-base-v2

# Processing Configuration
DEFAULT_THRESHOLD=0.75
MAX_SOURCES_PER_REQUEST=100
MAX_ANSWER_LENGTH=10000

# Feature Flags
ENABLE_FINGERPRINTING=true
ENABLE_METRICS=true
```

**5. Initialize Database Schema**

```bash
python -m auditor.storage.init_db
```

**6. Run Development Server**

```bash
# With auto-reload for development
uvicorn auditor.api.server:app --reload --port 8000

# With custom log level
uvicorn auditor.api.server:app --reload --port 8000 --log-level debug
```

### Option 2: Docker Development

**1. Build and Start Services**

```bash
# Build images and start all services
docker compose up --build

# Or run in detached mode
docker compose up -d

# View logs
docker compose logs -f auditor-api
```

**2. Access Services**

- API: http://localhost:8888
- API Docs: http://localhost:8888/docs
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3333 (admin/admin)

**3. Run Commands in Container**

```bash
# Run tests
docker compose exec auditor-api pytest

# Access Python shell
docker compose exec auditor-api python

# Run database migrations
docker compose exec auditor-api python -m auditor.storage.init_db
```

### Option 3: Dev Containers (VS Code)

If you use VS Code, you can use the provided dev container configuration:

```bash
# Open the project in VS Code
code .

# Press Ctrl+Shift+P (Cmd+Shift+P on Mac)
# Select: "Dev Containers: Reopen in Container"

# Wait for container to build and start
# All dependencies will be pre-installed
```

## Project Structure

```
juragpt-auditor/
├── auditor/                    # Main application package
│   ├── api/                    # FastAPI application
│   │   ├── server.py           # API server and routes
│   │   ├── models.py           # Pydantic request/response models
│   │   └── dependencies.py     # Dependency injection
│   ├── core/                   # Core business logic
│   │   ├── verification_service.py  # Main verification orchestration
│   │   ├── sentence_processor.py   # Sentence segmentation and NLP
│   │   ├── semantic_matcher.py     # Embedding-based matching
│   │   ├── confidence_engine.py    # Multi-factor confidence scoring
│   │   └── fingerprint_tracker.py  # Source fingerprinting
│   ├── storage/                # Database layer
│   │   ├── interface.py        # Storage abstraction
│   │   ├── sqlalchemy_storage.py  # SQLAlchemy implementation
│   │   ├── models.py           # Database models
│   │   └── init_db.py          # Database initialization
│   ├── config/                 # Configuration management
│   │   └── settings.py         # Settings with Pydantic
│   └── utils/                  # Utility functions
│       ├── logging.py          # Structured logging
│       └── metrics.py          # Prometheus metrics
├── tests/                      # Test suite
│   ├── unit/                   # Unit tests
│   ├── integration/            # Integration tests
│   └── conftest.py             # Pytest fixtures
├── docs/                       # Documentation
├── docker/                     # Docker configurations
├── monitoring/                 # Monitoring configs (Prometheus, Grafana)
├── .github/                    # GitHub Actions workflows
├── pyproject.toml              # Project metadata and dependencies
├── Dockerfile                  # Multi-stage production Dockerfile
├── docker-compose.yml          # Local development stack
└── README.md                   # Project overview
```

## Code Style Guidelines

We follow strict code quality standards to ensure maintainability and consistency.

### Python Style Guide

We use **PEP 8** with some modifications. Code style is enforced by automated tools.

**Formatting**: Black (line length: 100)
```bash
# Format all Python files
black auditor/ tests/

# Check formatting without making changes
black --check auditor/ tests/
```

**Linting**: Ruff (replaces Flake8, isort, etc.)
```bash
# Run linter
ruff check auditor/ tests/

# Auto-fix issues where possible
ruff check --fix auditor/ tests/
```

**Type Checking**: mypy
```bash
# Run type checker
mypy auditor/

# Strict mode is enabled in pyproject.toml
```

### Code Style Rules

**1. Imports**

```python
# Standard library imports
import json
import logging
from typing import List, Optional, Dict, Any

# Third-party imports
import numpy as np
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# Local imports
from auditor.core.verification_service import VerificationService
from auditor.storage.interface import StorageInterface
```

**2. Type Hints**

All functions must have type hints:

```python
# ✅ Good
def calculate_confidence(
    semantic_score: float,
    citation_score: float,
    source_score: float
) -> float:
    return (semantic_score * 0.5 + citation_score * 0.3 + source_score * 0.2)

# ❌ Bad
def calculate_confidence(semantic_score, citation_score, source_score):
    return (semantic_score * 0.5 + citation_score * 0.3 + source_score * 0.2)
```

**3. Docstrings**

Use Google-style docstrings for all public functions and classes:

```python
def verify_answer(
    answer: str,
    sources: List[Dict[str, Any]],
    threshold: float = 0.75
) -> Dict[str, Any]:
    """
    Verify an LLM-generated answer against source documents.

    Args:
        answer: The LLM-generated answer to verify
        sources: List of source documents with text and metadata
        threshold: Minimum confidence threshold (0.0 to 1.0)

    Returns:
        Dict containing verification results with confidence scores,
        trust labels, and detailed sentence analysis

    Raises:
        ValueError: If answer is empty or sources list is empty
        HTTPException: If verification processing fails

    Example:
        >>> result = verify_answer(
        ...     answer="Nach § 823 BGB haftet der Schädiger.",
        ...     sources=[{"text": "...", "source_id": "bgb_823"}],
        ...     threshold=0.75
        ... )
        >>> result["overall_confidence"]
        0.92
    """
    # Implementation
```

**4. Function and Variable Naming**

```python
# Functions and variables: snake_case
def calculate_semantic_similarity(text1: str, text2: str) -> float:
    semantic_score = compute_cosine_similarity(text1, text2)
    return semantic_score

# Classes: PascalCase
class VerificationService:
    pass

# Constants: UPPER_SNAKE_CASE
MAX_SOURCES_PER_REQUEST = 100
DEFAULT_THRESHOLD = 0.75

# Private methods: _leading_underscore
def _internal_helper_function():
    pass
```

**5. Error Handling**

```python
# Use specific exceptions with descriptive messages
def process_request(data: Dict[str, Any]) -> Dict[str, Any]:
    if not data.get("answer"):
        raise ValueError("Answer field is required and cannot be empty")

    if not data.get("sources"):
        raise ValueError("At least one source document is required")

    try:
        result = self._verify(data["answer"], data["sources"])
        return result
    except Exception as e:
        logger.error(f"Verification failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Verification processing failed: {str(e)}"
        )
```

**6. Logging**

```python
import logging

logger = logging.getLogger(__name__)

# Use appropriate log levels
logger.debug("Processing sentence: %s", sentence)  # Verbose details
logger.info("Verification completed for %d sentences", len(sentences))  # Important events
logger.warning("Low confidence score: %.2f", confidence)  # Potential issues
logger.error("Database connection failed", exc_info=True)  # Errors with stack trace
```

### Configuration Files

**pyproject.toml** defines all style rules:

```toml
[tool.black]
line-length = 100
target-version = ['py311']

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.mypy]
python_version = "3.11"
strict = true
warn_return_any = true
warn_unused_configs = true
```

## Testing Requirements

We maintain high test coverage to ensure code quality and reliability.

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov=auditor --cov-report=html --cov-report=term

# Run specific test file
pytest tests/unit/test_verification_service.py

# Run specific test function
pytest tests/unit/test_verification_service.py::test_verify_simple_answer

# Run tests with verbose output
pytest -v

# Run tests in parallel (faster)
pytest -n auto
```

### Test Structure

**Unit Tests** (`tests/unit/`): Test individual components in isolation

```python
# tests/unit/test_confidence_engine.py
import pytest
from auditor.core.confidence_engine import ConfidenceEngine

def test_calculate_confidence_high_scores():
    """Test confidence calculation with high component scores."""
    engine = ConfidenceEngine()

    confidence = engine.calculate_confidence(
        semantic_score=0.95,
        citation_score=0.90,
        source_score=0.85
    )

    assert confidence >= 0.90
    assert confidence <= 1.0

def test_calculate_confidence_low_scores():
    """Test confidence calculation with low component scores."""
    engine = ConfidenceEngine()

    confidence = engine.calculate_confidence(
        semantic_score=0.50,
        citation_score=0.45,
        source_score=0.55
    )

    assert confidence < 0.60
```

**Integration Tests** (`tests/integration/`): Test component interactions

```python
# tests/integration/test_verification_flow.py
import pytest
from auditor.core.verification_service import VerificationService
from auditor.storage.sqlalchemy_storage import SQLAlchemyStorage

@pytest.fixture
def verification_service(test_db):
    """Create verification service with test database."""
    storage = SQLAlchemyStorage(database_url=test_db)
    return VerificationService(storage=storage)

def test_end_to_end_verification(verification_service):
    """Test complete verification flow from request to result."""
    answer = "Nach § 823 BGB haftet, wer vorsätzlich einen Schaden verursacht."
    sources = [
        {
            "text": "Wer vorsätzlich oder fahrlässig das Leben...",
            "source_id": "bgb_823",
            "score": 0.95
        }
    ]

    result = verification_service.verify(answer, sources, threshold=0.75)

    assert result["overall_confidence"] > 0.0
    assert "trust_label" in result
    assert len(result["sentence_results"]) > 0
```

**Fixtures** (`tests/conftest.py`): Shared test utilities

```python
# tests/conftest.py
import pytest
from auditor.storage.interface import StorageInterface

@pytest.fixture
def mock_storage():
    """Create a mock storage interface for testing."""
    class MockStorage(StorageInterface):
        def __init__(self):
            self.results = []

        def save_verification_result(self, result):
            self.results.append(result)

        def get_verification_result(self, result_id):
            return next((r for r in self.results if r["id"] == result_id), None)

    return MockStorage()

@pytest.fixture(scope="session")
def test_db():
    """Create a test database."""
    # Setup
    db_url = "postgresql://auditor:auditor@localhost:5432/auditor_test"
    # Initialize schema
    # ...
    yield db_url
    # Teardown
    # Drop test database
```

### Coverage Requirements

- **Minimum coverage**: 80% overall
- **Critical components**: 90%+ coverage
  - `auditor.core.*`
  - `auditor.api.server`
  - `auditor.storage.*`

Check coverage report:

```bash
pytest --cov=auditor --cov-report=html
open htmlcov/index.html  # View detailed coverage report
```

### Writing Good Tests

**DO**:
- ✅ Test one thing per test function
- ✅ Use descriptive test names
- ✅ Arrange-Act-Assert pattern
- ✅ Use fixtures for setup/teardown
- ✅ Test edge cases and error conditions
- ✅ Mock external dependencies

**DON'T**:
- ❌ Test implementation details
- ❌ Write tests that depend on other tests
- ❌ Use hard-coded values without explanation
- ❌ Skip tests without a good reason
- ❌ Test third-party library functionality

## Git Workflow

We follow a **feature branch workflow** with pull requests.

### Branch Naming

Use descriptive branch names with prefixes:

```bash
# Feature branches
git checkout -b feature/add-batch-verification
git checkout -b feature/improve-citation-extraction

# Bug fixes
git checkout -b fix/confidence-calculation-error
git checkout -b fix/database-connection-leak

# Documentation
git checkout -b docs/update-api-reference
git checkout -b docs/add-deployment-guide

# Performance improvements
git checkout -b perf/optimize-embedding-cache
git checkout -b perf/reduce-memory-usage

# Refactoring
git checkout -b refactor/extract-nlp-module
git checkout -b refactor/simplify-api-responses
```

### Commit Messages

Follow **Conventional Commits** format:

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types**:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `perf`: Performance improvements
- `test`: Adding or updating tests
- `chore`: Maintenance tasks (dependencies, build, etc.)

**Examples**:

```bash
# Simple commit
git commit -m "feat(api): add batch verification endpoint"

# Detailed commit
git commit -m "fix(confidence): correct weighted average calculation

The confidence engine was using simple average instead of weighted
average for component scores. This led to incorrect overall confidence
values when component scores varied significantly.

Changes:
- Updated calculate_confidence() to use weighted average
- Added test cases for edge cases
- Updated documentation

Fixes #123"

# Breaking change
git commit -m "feat(api)!: change response format for verification results

BREAKING CHANGE: The verification API now returns results in a different
format. The 'sentences' field has been renamed to 'sentence_results' and
now includes additional metadata.

Migration guide: Update client code to use 'sentence_results' instead
of 'sentences'."
```

### Keeping Your Fork Up to Date

```bash
# Fetch changes from upstream
git fetch upstream

# Merge upstream changes into your main branch
git checkout main
git merge upstream/main

# Push updated main to your fork
git push origin main

# Rebase your feature branch on latest main
git checkout feature/your-feature
git rebase main
```

## Pull Request Process

### Before Creating a PR

1. **Update your branch** with the latest main:
   ```bash
   git checkout main
   git pull upstream main
   git checkout feature/your-feature
   git rebase main
   ```

2. **Run all checks locally**:
   ```bash
   # Format code
   black auditor/ tests/

   # Lint code
   ruff check --fix auditor/ tests/

   # Type check
   mypy auditor/

   # Run tests
   pytest --cov=auditor

   # Build (if applicable)
   docker compose build
   ```

3. **Write/update tests** for your changes

4. **Update documentation** if needed

### Creating a PR

1. **Push your branch** to your fork:
   ```bash
   git push origin feature/your-feature
   ```

2. **Create PR on GitHub** with a descriptive title and description

3. **Fill out the PR template**:
   ```markdown
   ## Description
   Brief description of what this PR does

   ## Type of Change
   - [ ] Bug fix (non-breaking change which fixes an issue)
   - [ ] New feature (non-breaking change which adds functionality)
   - [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
   - [ ] Documentation update

   ## Testing
   - [ ] Unit tests pass
   - [ ] Integration tests pass
   - [ ] Manual testing completed

   ## Checklist
   - [ ] Code follows project style guidelines
   - [ ] Self-review completed
   - [ ] Comments added for complex logic
   - [ ] Documentation updated
   - [ ] No new warnings generated

   ## Related Issues
   Fixes #123
   Related to #456
   ```

4. **Link related issues** using keywords:
   - `Fixes #123` - Closes the issue when PR is merged
   - `Closes #123` - Same as Fixes
   - `Related to #123` - References the issue without closing

### PR Review Process

1. **Automated checks** must pass:
   - Code formatting (Black)
   - Linting (Ruff)
   - Type checking (mypy)
   - Tests (pytest)
   - Coverage threshold

2. **Code review** by at least one maintainer

3. **Address review comments**:
   ```bash
   # Make changes based on feedback
   git add .
   git commit -m "Address review comments"
   git push origin feature/your-feature
   ```

4. **Approval and merge**:
   - Maintainer approves the PR
   - Maintainer merges using "Squash and merge" (for clean history)

## Code Review Checklist

### For Authors

Before requesting review:

- [ ] **Code quality**
  - [ ] Follows project style guidelines (Black, Ruff, mypy pass)
  - [ ] No commented-out code or debug statements
  - [ ] Complex logic has comments explaining why (not what)
  - [ ] No unnecessary dependencies added

- [ ] **Testing**
  - [ ] New features have unit tests
  - [ ] Edge cases are tested
  - [ ] Tests pass locally (`pytest`)
  - [ ] Coverage meets minimum threshold

- [ ] **Documentation**
  - [ ] Docstrings for new functions/classes
  - [ ] README updated if user-facing changes
  - [ ] API docs updated if endpoints changed
  - [ ] Comments for non-obvious code

- [ ] **Performance**
  - [ ] No obvious performance regressions
  - [ ] Database queries are efficient
  - [ ] Memory usage is reasonable

- [ ] **Security**
  - [ ] No sensitive data in code or logs
  - [ ] Input validation for all user inputs
  - [ ] No SQL injection vulnerabilities

### For Reviewers

When reviewing PRs:

- [ ] **Correctness**
  - [ ] Code does what it's supposed to do
  - [ ] Edge cases are handled
  - [ ] Error handling is appropriate

- [ ] **Code quality**
  - [ ] Easy to understand and maintain
  - [ ] Follows DRY principle (Don't Repeat Yourself)
  - [ ] Appropriate abstractions
  - [ ] Consistent with existing codebase

- [ ] **Tests**
  - [ ] Tests are meaningful and test the right things
  - [ ] Tests are not too coupled to implementation
  - [ ] Test names are descriptive

- [ ] **Design**
  - [ ] Solution is appropriate for the problem
  - [ ] No over-engineering
  - [ ] Follows SOLID principles where applicable

- [ ] **Documentation**
  - [ ] Changes are well-documented
  - [ ] Complex logic is explained

## Reporting Bugs

### Before Reporting

1. **Check existing issues** - Your bug may already be reported
2. **Try latest version** - Bug may already be fixed
3. **Verify it's a bug** - Ensure expected behavior is incorrect

### Bug Report Template

```markdown
**Description**
Clear and concise description of the bug.

**To Reproduce**
Steps to reproduce:
1. Call endpoint '...'
2. With payload '...'
3. See error

**Expected Behavior**
What you expected to happen.

**Actual Behavior**
What actually happened.

**Environment**
- OS: [e.g., Ubuntu 22.04]
- Python version: [e.g., 3.11.5]
- JuraGPT Auditor version: [e.g., 0.1.0]
- Deployment: [Docker / Local / Cloud]

**Error Logs**
```
Paste relevant error logs here
```

**Additional Context**
Any other information about the problem.
```

## Requesting Features

### Feature Request Template

```markdown
**Problem Statement**
What problem does this feature solve?

**Proposed Solution**
Describe your proposed solution.

**Alternatives Considered**
Other approaches you've considered.

**Use Case**
Example scenario where this would be useful.

**Additional Context**
Any other relevant information.
```

## Community Guidelines

### Communication Channels

- **GitHub Issues**: Bug reports, feature requests
- **GitHub Discussions**: Questions, ideas, general discussion
- **Pull Requests**: Code contributions

### Response Times

- Issues are typically reviewed within **2-3 business days**
- PRs are typically reviewed within **3-5 business days**
- Security issues are reviewed within **24 hours**

### Contribution Recognition

All contributors are recognized in:
- Release notes
- Contributors list in README
- Project documentation

## Development Best Practices

### Performance

1. **Profile before optimizing**: Use profilers to identify bottlenecks
   ```bash
   python -m cProfile -o profile.stats -m auditor.api.server
   ```

2. **Cache expensive operations**: Use `@lru_cache` for pure functions
   ```python
   from functools import lru_cache

   @lru_cache(maxsize=1000)
   def compute_embedding(text: str) -> np.ndarray:
       return model.encode(text)
   ```

3. **Batch processing**: Process multiple items together when possible

4. **Database optimization**: Use indexes, batch inserts, connection pooling

### Security

1. **Input validation**: Validate all user inputs with Pydantic
2. **SQL injection**: Use parameterized queries (SQLAlchemy ORM)
3. **Secrets management**: Never commit secrets, use environment variables
4. **Dependency scanning**: Run `pip-audit` regularly

### Logging

1. **Use structured logging**: Include context in log messages
   ```python
   logger.info(
       "Verification completed",
       extra={
           "answer_length": len(answer),
           "num_sources": len(sources),
           "confidence": result["overall_confidence"]
       }
   )
   ```

2. **Appropriate log levels**: DEBUG for verbose, INFO for events, WARNING for issues, ERROR for failures

3. **No sensitive data**: Never log passwords, tokens, or personal information

### Error Handling

1. **Specific exceptions**: Catch specific exceptions, not bare `except:`
2. **Context in errors**: Include relevant information in error messages
3. **Fail gracefully**: Handle errors without crashing the application
4. **Logging with stack traces**: Use `exc_info=True` for error logs

### Database

1. **Use transactions**: Wrap related operations in transactions
2. **Connection management**: Use context managers for database connections
3. **Migration scripts**: Use Alembic for schema changes (coming soon)
4. **Query optimization**: Use explain analyze to optimize slow queries

### API Design

1. **RESTful principles**: Follow REST conventions for endpoints
2. **Versioning**: Use API versioning for breaking changes
3. **Pagination**: Paginate large result sets
4. **Error responses**: Return consistent error response format

## Getting Help

If you need help contributing:

1. **Check documentation**: README, ARCHITECTURE, API docs
2. **Search existing issues**: Your question may already be answered
3. **Ask in discussions**: Open a GitHub Discussion for questions
4. **Contact maintainers**: For sensitive issues or urgent questions

---

Thank you for contributing to JuraGPT Auditor! 🎉

Your contributions help make legal AI verification more reliable and trustworthy.
