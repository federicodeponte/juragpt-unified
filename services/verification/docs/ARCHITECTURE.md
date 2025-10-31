# Architecture

Comprehensive architectural documentation for the JuraGPT Auditor verification service.

## Table of Contents

- [Overview](#overview)
- [Design Principles](#design-principles)
- [System Architecture](#system-architecture)
- [Component Design](#component-design)
- [Data Flow](#data-flow)
- [Database Schema](#database-schema)
- [Scalability](#scalability)
- [Performance](#performance)
- [Security](#security)
- [Operational Concerns](#operational-concerns)
- [Technology Choices](#technology-choices)
- [Future Enhancements](#future-enhancements)

---

## Overview

The JuraGPT Auditor is a production-grade microservice designed to detect hallucinations in LLM-generated legal answers by performing sentence-level semantic verification against trusted source documents.

### Key Characteristics

- **Stateless Design**: Each request is independent, enabling horizontal scaling
- **Async Processing**: Non-blocking I/O for optimal throughput
- **Modular Architecture**: Clean separation of concerns with dependency injection
- **Type-Safe**: Full mypy coverage for compile-time safety
- **Observable**: Prometheus metrics and structured logging throughout
- **Extensible**: Domain-agnostic core with pluggable domain modules

---

## Design Principles

### 1. Separation of Concerns

Each component has a single, well-defined responsibility:

```
API Layer         → HTTP interface, validation, serialization
Service Layer     → Business logic, orchestration
Processing Layer  → NLP, semantic matching, scoring
Storage Layer     → Data persistence, retrieval
Domain Layer      → Domain-specific logic (legal citations, etc.)
```

### 2. Dependency Injection

Components receive their dependencies via constructor injection:

```python
class VerificationService:
    def __init__(
        self,
        sentence_processor: SentenceProcessor,
        semantic_matcher: SemanticMatcher,
        confidence_engine: ConfidenceEngine,
        storage: StorageInterface,
        fingerprint_tracker: FingerprintTracker
    ):
        self.sentence_processor = sentence_processor
        self.semantic_matcher = semantic_matcher
        # ...
```

**Benefits:**
- Testability: Easy to mock dependencies
- Flexibility: Swap implementations without changing code
- Explicitness: All dependencies declared upfront

### 3. Type Safety

Full type annotations with mypy strict mode:

```python
def verify_answer(
    self,
    answer: str,
    sources: List[Source],
    threshold: float = 0.75,
    strict_mode: bool = False
) -> VerificationResult:
    # ...
```

**Benefits:**
- Catch errors at development time
- IDE auto-completion and navigation
- Self-documenting code

### 4. Observable by Design

Metrics, logging, and tracing built into every component:

```python
VERIFY_REQUESTS = Counter('auditor_verify_requests_total', ...)
VERIFY_LATENCY = Histogram('auditor_verify_latency_seconds', ...)

@VERIFY_LATENCY.time()
def verify_answer(...) -> VerificationResult:
    VERIFY_REQUESTS.labels(status='success').inc()
    # ...
```

### 5. Fail-Safe Defaults

Graceful degradation instead of failures:

- Missing models → Fall back to basic string matching
- Database errors → Return verification results without storage
- Cache misses → Calculate embeddings on-demand
- Low confidence → Auto-retry with different parameters

---

## System Architecture

### Layered Architecture

```
┌────────────────────────────────────────────────────────────────┐
│                       Presentation Layer                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │   FastAPI    │  │   Pydantic   │  │   OpenAPI    │         │
│  │   Endpoints  │  │   Models     │  │     Docs     │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
└────────────────────────────┬───────────────────────────────────┘
                             │
┌────────────────────────────▼───────────────────────────────────┐
│                        Service Layer                            │
│  ┌─────────────────────────────────────────────────┐           │
│  │         Verification Service                     │           │
│  │  • Orchestrates verification workflow            │           │
│  │  • Handles auto-retry logic                      │           │
│  │  • Manages metrics and logging                   │           │
│  └─────────────────────────────────────────────────┘           │
└────────────────────────────┬───────────────────────────────────┘
                             │
┌────────────────────────────▼───────────────────────────────────┐
│                       Processing Layer                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │  Sentence    │  │   Semantic   │  │  Confidence  │         │
│  │  Processor   │  │   Matcher    │  │    Engine    │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
│  ┌──────────────┐                                              │
│  │ Fingerprint  │                                              │
│  │   Tracker    │                                              │
│  └──────────────┘                                              │
└────────────────────────────┬───────────────────────────────────┘
                             │
┌────────────────────────────▼───────────────────────────────────┐
│                        Storage Layer                            │
│  ┌─────────────────────────────────────────────────┐           │
│  │         Storage Interface                        │           │
│  │  • Abstracts database operations                 │           │
│  │  • Session management                            │           │
│  │  • Query optimization                            │           │
│  └─────────────────────────────────────────────────┘           │
└────────────────────────────┬───────────────────────────────────┘
                             │
┌────────────────────────────▼───────────────────────────────────┐
│                      Infrastructure Layer                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐         │
│  │  PostgreSQL  │  │  Prometheus  │  │   Grafana    │         │
│  │   Database   │  │    Metrics   │  │  Dashboards  │         │
│  └──────────────┘  └──────────────┘  └──────────────┘         │
└─────────────────────────────────────────────────────────────────┘
```

### Component Relationships

```
┌─────────────────────────────────────────────────────────────┐
│                      FastAPI Application                     │
└────────────────┬────────────────────────────────────────────┘
                 │
                 │ Creates via dependency injection
                 │
                 ▼
┌─────────────────────────────────────────────────────────────┐
│                  Verification Service                        │
│  ┌───────────────────────────────────────────────────┐      │
│  │ Dependencies (injected):                          │      │
│  │ • SentenceProcessor                               │      │
│  │ • SemanticMatcher                                 │      │
│  │ • ConfidenceEngine                                │      │
│  │ • StorageInterface                                │      │
│  │ • FingerprintTracker                              │      │
│  └───────────────────────────────────────────────────┘      │
└───┬──────┬──────┬──────┬──────────────────────────────────────┘
    │      │      │      │
    │      │      │      └──────────────────┐
    │      │      │                         │
    ▼      ▼      ▼                         ▼
┌────┐ ┌────┐ ┌────┐                  ┌─────────┐
│ SP │ │ SM │ │ CE │                  │   FT    │
└─┬──┘ └─┬──┘ └────┘                  └─────────┘
  │      │
  │      └─────────────┐
  │                    │
  ▼                    ▼
┌────────────┐    ┌────────────┐
│   spaCy    │    │sentence-   │
│   Model    │    │transformers│
└────────────┘    └────────────┘

All components access:
                 ▼
         ┌──────────────┐
         │   Storage    │
         │  Interface   │
         └──────┬───────┘
                │
                ▼
         ┌──────────────┐
         │  PostgreSQL  │
         └──────────────┘

Legend:
SP = SentenceProcessor
SM = SemanticMatcher
CE = ConfidenceEngine
FT = FingerprintTracker
```

---

## Component Design

### 1. API Layer (FastAPI)

**Responsibility**: HTTP interface, request validation, response serialization

**Files**:
- `src/auditor/api/server.py` - FastAPI application setup
- `src/auditor/api/models.py` - Pydantic request/response models

**Design Patterns**:
- **Dependency Injection**: Services injected via `Depends()`
- **Lifespan Management**: Modern startup/shutdown with `@asynccontextmanager`
- **Exception Handling**: Global exception handlers for consistent error responses

**Key Design Decisions**:

1. **Pydantic for Validation**:
   ```python
   class VerificationRequest(BaseModel):
       answer: str = Field(..., min_length=1, max_length=10000)
       sources: List[Source] = Field(..., min_items=1, max_items=100)
       threshold: float = Field(0.75, ge=0.0, le=1.0)
       strict_mode: bool = Field(False)
   ```
   - Automatic validation and error messages
   - Type coercion where appropriate
   - Self-documenting with Field descriptions

2. **OpenAPI Documentation**:
   - Automatic from Pydantic models
   - Examples embedded in models
   - Accessible at `/docs` and `/redoc`

3. **Health Checks**:
   ```python
   @app.get("/health")
   async def health_check() -> HealthResponse:
       return HealthResponse(
           status="healthy",
           version=__version__,
           models={"spacy": "de_core_news_md", ...}
       )
   ```

### 2. Verification Service

**Responsibility**: Orchestrate verification workflow, implement business logic

**File**: `src/auditor/core/verification_service.py`

**Architecture**:

```python
class VerificationService:
    """
    Core orchestrator for answer verification.

    Workflow:
    1. Parse answer into sentences
    2. Extract citations from each sentence
    3. Match sentences to source documents
    4. Calculate confidence scores
    5. Determine trust labels
    6. Auto-retry if needed
    7. Store results and fingerprints
    """

    def __init__(self, ...):
        # Dependencies injected

    def verify_answer(
        self,
        answer: str,
        sources: List[Source],
        threshold: float,
        strict_mode: bool
    ) -> VerificationResult:
        # Main verification logic
```

**Key Algorithms**:

1. **Sentence Matching**:
   ```
   For each sentence in answer:
       1. Get sentence embedding (E5-large)
       2. Compare to all source embeddings (cosine similarity)
       3. Select best match above threshold
       4. Extract explanations
   ```

2. **Confidence Scoring**:
   ```
   confidence = weighted_average(
       semantic_similarity * 0.50,
       retrieval_score * 0.25,
       citation_coverage * 0.15,
       overall_coverage * 0.10
   )
   ```

3. **Auto-Retry Logic**:
   ```python
   if confidence < retry_threshold and retries < max_retries:
       # Adjust parameters and retry
       result = self.verify_answer(
           answer, sources,
           threshold=threshold * 0.9,  # Lower threshold
           strict_mode=False  # Relax strictness
       )
   ```

### 3. Sentence Processor

**Responsibility**: NLP operations (tokenization, citation extraction)

**File**: `src/auditor/core/sentence_processor.py`

**Architecture**:

```python
class SentenceProcessor:
    def __init__(self, language_module, domain_module):
        self.language_module = language_module  # spaCy model
        self.domain_module = domain_module      # Domain-specific (e.g., GermanLegalDomain)

    def split_into_sentences(self, text: str) -> List[str]:
        # Use spaCy's sentence segmentation

    def extract_citations(self, text: str) -> List[str]:
        # Delegate to domain module
        return self.domain_module.get_citation_patterns(text)
```

**Domain Module Pattern**:

```python
class DomainModule(ABC):
    @abstractmethod
    def get_citation_patterns(self) -> List[str]:
        """Return regex patterns for citations."""

    @abstractmethod
    def extract_citations(self, text: str) -> List[str]:
        """Extract citations from text."""

class GermanLegalDomain(DomainModule):
    def get_citation_patterns(self) -> List[str]:
        return [
            r'§\s*\d+[a-z]?\s+[A-Z]{2,}',  # § 823 BGB
            r'Art\.\s*\d+[a-z]?\s+[A-Z]{2,}',  # Art. 1 GG
            # ...
        ]
```

**Extensibility**: Add new domains by implementing `DomainModule`.

### 4. Semantic Matcher

**Responsibility**: Embedding generation, similarity calculation

**File**: `src/auditor/core/semantic_matcher.py`

**Architecture**:

```python
class SemanticMatcher:
    def __init__(self, model_name: str = "intfloat/multilingual-e5-large"):
        self.model = SentenceTransformer(model_name)
        self.cache = {}  # LRU cache for embeddings

    def get_embedding(self, text: str) -> np.ndarray:
        # Check cache first, compute if needed

    def find_best_matches(
        self,
        query: str,
        candidates: List[str],
        top_k: int = 5
    ) -> List[Match]:
        # Compute embeddings, calculate cosine similarity
```

**Caching Strategy**:

```python
# LRU cache with max size
cache_size = 1000  # Configurable

def get_embedding(self, text: str) -> np.ndarray:
    cache_key = hashlib.md5(text.encode()).hexdigest()

    if cache_key in self.cache:
        self.cache_hits.inc()
        return self.cache[cache_key]

    self.cache_misses.inc()
    embedding = self.model.encode(text)

    if len(self.cache) >= self.cache_size:
        self.cache.popitem(last=False)  # Remove oldest

    self.cache[cache_key] = embedding
    return embedding
```

**Performance Optimization**:
- Batch encoding when possible
- GPU acceleration if available (CUDA)
- Quantization for reduced memory (FP16 vs FP32)

### 5. Confidence Engine

**Responsibility**: Multi-factor scoring, trust label assignment

**File**: `src/auditor/core/confidence_engine.py`

**Scoring Algorithm**:

```python
def calculate_confidence(
    self,
    sentence_result: SentenceResult,
    all_sources: List[Source],
    answer_citations: List[str]
) -> float:
    """
    Multi-factor confidence score:

    1. Semantic Quality (50%):
       - How well does the sentence match the best source?
       - Cosine similarity of embeddings

    2. Retrieval Quality (25%):
       - Was the source highly relevant in retrieval?
       - Uses original retrieval score from RAG system

    3. Citation Coverage (15%):
       - Does the sentence cite sources appropriately?
       - Ratio of citations found to expected

    4. Overall Coverage (10%):
       - Are all answer citations covered by sources?
       - Ensures no unsupported claims
    """

    semantic = sentence_result.similarity * 0.50
    retrieval = sentence_result.best_match.score * 0.25
    citation = self._citation_coverage(sentence_result, answer_citations) * 0.15
    overall = self._overall_coverage(answer_citations, all_sources) * 0.10

    return semantic + retrieval + citation + overall
```

**Trust Label Thresholds**:

```python
def assign_trust_label(self, confidence: float) -> str:
    if confidence >= 0.90:
        return "Verified (High Confidence)"
    elif confidence >= 0.80:
        return "Verified (Moderate Confidence)"
    elif confidence >= 0.60:
        return "Review Required (Low Confidence)"
    else:
        return "Rejected (Very Low Confidence)"
```

**Configurable**: Thresholds adjustable via configuration.

### 6. Storage Interface

**Responsibility**: Database abstraction, session management

**File**: `src/auditor/storage/interface.py`

**Architecture**:

```python
class StorageInterface:
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.SessionLocal, self.engine = create_database(database_url)

    def store_verification_result(self, result: VerificationResult) -> int:
        with self.SessionLocal() as session:
            db_result = VerificationResultModel(**result.dict())
            session.add(db_result)
            session.commit()
            return db_result.id

    def get_verification_result(self, result_id: int) -> Optional[VerificationResult]:
        with self.SessionLocal() as session:
            db_result = session.query(VerificationResultModel).filter_by(id=result_id).first()
            return VerificationResult(**db_result.dict()) if db_result else None
```

**Session Management**:
- Context managers for automatic cleanup
- Connection pooling via SQLAlchemy
- Retry logic for transient errors

### 7. Fingerprint Tracker

**Responsibility**: Detect source changes via SHA-256 hashing

**File**: `src/auditor/core/fingerprint_tracker.py`

**Architecture**:

```python
class FingerprintTracker:
    def generate_fingerprint(self, source: Source) -> str:
        """SHA-256 hash of source text."""
        return hashlib.sha256(source.text.encode('utf-8')).hexdigest()

    def check_source_changed(
        self,
        source_id: str,
        current_fingerprint: str
    ) -> bool:
        """Compare against stored fingerprint."""
        last_known = self.storage.get_latest_fingerprint(source_id)
        return last_known != current_fingerprint
```

**Use Cases**:
- **Source Versioning**: Track when sources are updated
- **Cache Invalidation**: Invalidate embeddings when source changes
- **Audit Trail**: History of source modifications

---

## Data Flow

### Verification Request Flow

```
1. Client Request
   │
   ├─→ POST /verify
   │   Headers: Content-Type: application/json
   │   Body: { answer, sources, threshold, strict_mode }
   │
2. FastAPI Layer
   │
   ├─→ Request Validation (Pydantic)
   ├─→ Dependency Injection (VerificationService)
   │
3. Verification Service
   │
   ├─→ Parse answer into sentences (SentenceProcessor)
   │   └─→ spaCy sentence segmentation
   │
   ├─→ Extract citations (SentenceProcessor → DomainModule)
   │   └─→ Regex pattern matching
   │
   ├─→ For each sentence:
   │   ├─→ Get sentence embedding (SemanticMatcher)
   │   │   └─→ Check cache → Compute if miss → Store in cache
   │   │
   │   ├─→ Get source embeddings (SemanticMatcher)
   │   │   └─→ Batch processing for efficiency
   │   │
   │   ├─→ Calculate similarities (SemanticMatcher)
   │   │   └─→ Cosine similarity (NumPy)
   │   │
   │   ├─→ Find best match (threshold filtering)
   │   │
   │   └─→ Calculate confidence (ConfidenceEngine)
   │       └─→ Multi-factor scoring
   │
   ├─→ Aggregate sentence results
   │   └─→ Overall confidence, trust label
   │
   ├─→ Auto-retry if needed
   │   └─→ Recursively call with adjusted parameters
   │
   ├─→ Generate fingerprints (FingerprintTracker)
   │   └─→ SHA-256 hashing
   │
   ├─→ Store results (StorageInterface)
   │   └─→ Database INSERT
   │
4. Response Serialization
   │
   ├─→ Convert to VerificationResponse (Pydantic)
   │
   └─→ Return JSON to client
```

### Database Interaction Flow

```
Storage Interface
      │
      ├─→ Session Creation
      │   └─→ SQLAlchemy SessionLocal()
      │
      ├─→ Query/Insert/Update
      │   ├─→ ORM Models (VerificationResultModel, etc.)
      │   └─→ SQL Generation (SQLAlchemy)
      │
      ├─→ Commit/Rollback
      │   └─→ Transaction management
      │
      └─→ Session Close
          └─→ Connection return to pool

PostgreSQL
      │
      ├─→ Connection Pooling (pgBouncer in production)
      │
      ├─→ Query Execution
      │   ├─→ Index usage (source_id, fingerprint)
      │   └─→ Query plan optimization
      │
      └─→ Result Return
```

---

## Database Schema

### ER Diagram

```
┌────────────────────────────────────┐
│   verification_results             │
├────────────────────────────────────┤
│ id (PK)                  SERIAL    │
│ answer                   TEXT      │
│ overall_confidence       FLOAT     │
│ trust_label              VARCHAR   │
│ overall_status           VARCHAR   │
│ created_at               TIMESTAMP │
│ processing_time_ms       FLOAT     │
│ model_name               VARCHAR   │
│ language                 VARCHAR   │
└────────────┬───────────────────────┘
             │
             │ 1:N
             │
┌────────────▼───────────────────────┐
│   sentence_results                 │
├────────────────────────────────────┤
│ id (PK)                  SERIAL    │
│ verification_result_id (FK) INT    │
│ sentence                 TEXT      │
│ confidence               FLOAT     │
│ status                   VARCHAR   │
│ best_match_source_id     VARCHAR   │
│ best_match_similarity    FLOAT     │
│ best_match_snippet       TEXT      │
│ citations_found          JSON      │
│ explanations             JSON      │
└────────────────────────────────────┘

┌────────────────────────────────────┐
│   source_fingerprints              │
├────────────────────────────────────┤
│ id (PK)                  SERIAL    │
│ source_id                VARCHAR   │
│ fingerprint              CHAR(64)  │
│ created_at               TIMESTAMP │
│ text_length              INT       │
└────────────────────────────────────┘
```

### Schema Design Decisions

1. **Normalized Structure**:
   - `verification_results` for overall verification
   - `sentence_results` for sentence-level details
   - Reduces data duplication, improves queryability

2. **Indexes**:
   ```sql
   CREATE INDEX idx_verification_results_created_at
       ON verification_results(created_at DESC);

   CREATE INDEX idx_sentence_results_verification_id
       ON sentence_results(verification_result_id);

   CREATE INDEX idx_source_fingerprints_source_id
       ON source_fingerprints(source_id, created_at DESC);
   ```

3. **JSON Columns**:
   - `citations_found`: Array of strings (flexible, no fixed schema)
   - `explanations`: Array of strings (variable length)
   - PostgreSQL JSONB for indexing and querying

4. **Timestamps**:
   - `created_at`: Audit trail, time-series analysis
   - Automatic via `default=datetime.utcnow`

---

## Scalability

### Horizontal Scaling

**Stateless Design** enables easy horizontal scaling:

```
┌────────────────┐
│ Load Balancer  │ (nginx, HAProxy, ALB)
└────────┬───────┘
         │
    ┌────┼────┬────┬────┐
    │    │    │    │    │
    ▼    ▼    ▼    ▼    ▼
┌─────┐┌─────┐┌─────┐┌─────┐┌─────┐
│API 1││API 2││API 3││API 4││API 5│
└──┬──┘└──┬──┘└──┬──┘└──┬──┘└──┬──┘
   │      │      │      │      │
   └──────┴──────┴──────┴──────┘
                 │
         ┌───────▼────────┐
         │   PostgreSQL   │
         │ (Connection    │
         │  Pooling)      │
         └────────────────┘
```

**Scaling Strategy**:

1. **Add More API Instances**:
   ```bash
   docker-compose up -d --scale auditor-api=5
   ```

2. **Load Balancing**:
   - Round-robin or least-connections
   - Health checks at `/health` endpoint

3. **Session Affinity**: NOT required (stateless)

### Vertical Scaling

**Resource-intensive components**:

1. **Embedding Calculation**:
   - CPU-bound for sentence-transformers
   - GPU acceleration recommended for high throughput
   - Scale: More CPU cores or GPU instances

2. **Database Queries**:
   - I/O-bound for large result sets
   - Scale: More RAM for caching, faster storage (NVMe SSD)

### Database Scaling

**Read/Write Split**:

```
┌─────────────┐
│ API Cluster │
└──┬──────┬───┘
   │      │
   │      └─────────────────┐
   │                        │
   ▼                        ▼
┌──────────┐         ┌──────────┐
│PostgreSQL│         │PostgreSQL│
│  Primary │─────────│ Replica 1│ (Read-only)
│ (Write)  │Streaming│          │
└──────────┘Replica  └──────────┘
                     ┌──────────┐
                     │PostgreSQL│
                     │ Replica 2│ (Read-only)
                     └──────────┘
```

**Sharding Strategy** (future):
- Shard by `source_id` or `verification_date`
- Requires application-level routing

### Caching Strategies

1. **Embedding Cache** (Application-level):
   - LRU cache in `SemanticMatcher`
   - Size: 1000 entries (configurable)
   - Hit rate: ~70-90% in production

2. **Redis Cache** (future):
   ```
   API → Redis (embedding cache) → sentence-transformers
   ```

3. **Database Query Cache**:
   - PostgreSQL built-in caching
   - Tune `shared_buffers`, `effective_cache_size`

---

## Performance

### Latency Breakdown

Typical 22ms request (1 sentence):

```
Total: 22ms
├─ Request parsing/validation: 1ms (4%)
├─ Sentence segmentation: 2ms (9%)
├─ Embedding lookup/compute: 12ms (55%)
│  ├─ Cache hit: 0.1ms
│  └─ Cache miss: 15ms (sentence-transformers)
├─ Similarity calculation: 3ms (14%)
├─ Confidence scoring: 2ms (9%)
├─ Database storage: 1ms (4%)
└─ Response serialization: 1ms (5%)
```

**Bottleneck**: Embedding computation (cache misses)

### Optimization Strategies

1. **Batch Processing**:
   ```python
   # Instead of:
   for sentence in sentences:
       embedding = model.encode(sentence)  # Slow

   # Do:
   embeddings = model.encode(sentences)  # Fast (batched)
   ```

2. **Embedding Cache**:
   - Pre-compute and cache common phrases
   - Warm cache on startup with frequent queries

3. **Database Optimization**:
   - Connection pooling (SQLAlchemy)
   - Prepared statements
   - Batch inserts for sentence results

4. **Async I/O** (future):
   - Current: Sync database calls
   - Future: Asyncio + asyncpg for concurrent queries

### Throughput

**Single Instance** (4 CPU, 8GB RAM):
- Simple queries (1 sentence): ~45 req/s
- Medium queries (5 sentences): ~12 req/s
- Complex queries (10 sentences): ~5 req/s

**5-Instance Cluster**:
- Linear scaling: 5x throughput
- Simple queries: ~225 req/s
- Medium queries: ~60 req/s

### Load Testing Results

```bash
# Locust load test (1000 users, 1-sentence queries)
Total requests: 50,000
Success rate: 99.97%
Average latency: 24ms
P95 latency: 180ms
P99 latency: 420ms
Throughput: 43 req/s per instance
```

---

## Security

### Authentication & Authorization

**Current State**: No authentication (internal service)

**Planned** (v1.1):
- JWT token authentication
- API key authentication
- Role-based access control (RBAC)

```python
@app.post("/verify")
async def verify_answer(
    request: VerificationRequest,
    user: User = Depends(get_current_user)  # JWT validation
):
    # Check user permissions
    if not user.has_permission("verify"):
        raise HTTPException(status_code=403)
    # ...
```

### Input Validation

**Defense Against**:
- SQL Injection: Using ORM (SQLAlchemy), parameterized queries
- XSS: Not applicable (JSON API, no HTML rendering)
- Command Injection: No shell commands executed
- Path Traversal: No file operations based on user input

**Validation Rules**:
```python
class VerificationRequest(BaseModel):
    answer: str = Field(..., min_length=1, max_length=10000)
    sources: List[Source] = Field(..., min_items=1, max_items=100)
    threshold: float = Field(0.75, ge=0.0, le=1.0)
```

### Rate Limiting

**Planned** (v1.1):
```python
from slowapi import Limiter

limiter = Limiter(key_func=get_remote_address)

@app.post("/verify")
@limiter.limit("100/minute")  # Per IP
async def verify_answer(...):
    ...
```

### Secrets Management

- API keys → Environment variables
- Database passwords → Environment variables
- Model paths → Configuration files
- No secrets in code or version control

---

## Operational Concerns

### Logging

**Structured Logging**:
```python
logger.info(
    "verification_completed",
    extra={
        "overall_confidence": result.overall_confidence,
        "trust_label": result.trust_label,
        "processing_time_ms": processing_time,
        "sentence_count": len(result.sentence_results)
    }
)
```

**Log Levels**:
- DEBUG: Detailed execution flow
- INFO: Request/response, key events
- WARNING: Retries, degraded performance
- ERROR: Failures, exceptions

### Monitoring (Prometheus)

**Key Metrics**:
- `auditor_verify_requests_total`: Counter by status, trust_label
- `auditor_verify_latency_seconds`: Histogram (percentiles)
- `auditor_confidence_score`: Histogram (distribution)
- `auditor_cache_hits_total` / `auditor_cache_misses_total`: Cache performance

**Alerting**: See [MONITORING.md](MONITORING.md) for runbook.

### Deployment

**Docker**: Multi-stage build with model caching
**Docker Compose**: Full stack (API + PostgreSQL + Prometheus + Grafana)
**Kubernetes** (future): Helm charts, auto-scaling

See [DEPLOYMENT.md](DEPLOYMENT.md) for details.

### Backup & Recovery

**Database Backups**:
- Daily backups via `pg_dump`
- Retention: 30 days
- Stored in S3 or equivalent

**Model Backups**:
- Models baked into Docker image
- Version controlled via image tags

**Configuration Backups**:
- Version controlled in Git

---

## Technology Choices

### Why FastAPI?

- **Performance**: Async support, fast (comparable to Node.js)
- **Developer Experience**: Auto-docs, type hints, validation
- **Ecosystem**: Wide adoption, active community

**Alternatives Considered**:
- Flask: Sync-only, less built-in validation
- Django: Too heavyweight for microservice

### Why spaCy?

- **Language Support**: Excellent German NLP models
- **Sentence Segmentation**: Better than NLTK for legal text
- **Performance**: Fast C++ backend

**Alternatives Considered**:
- NLTK: Slower, less accurate segmentation
- Stanza: Slower, more accurate (overkill for this use case)

### Why sentence-transformers?

- **State-of-the-art**: Best semantic embeddings for similarity
- **Multilingual**: E5-large supports 100+ languages
- **Efficiency**: Optimized inference, GPU support

**Alternatives Considered**:
- Word2Vec: Outdated, context-insensitive
- BERT: Requires custom pooling, slower

### Why PostgreSQL?

- **Reliability**: Battle-tested, ACID compliant
- **Features**: JSONB for semi-structured data, full-text search
- **Scalability**: Replication, sharding options

**Alternatives Considered**:
- MySQL: Less feature-rich
- MongoDB: Document store, no strong consistency

### Why Prometheus + Grafana?

- **Industry Standard**: De facto standard for cloud-native monitoring
- **Pull-based**: Scrapes metrics (no push required)
- **Powerful**: PromQL for complex queries
- **Visualization**: Grafana for dashboards

**Alternatives Considered**:
- Datadog: Expensive, vendor lock-in
- ELK Stack: Overkill for metrics (better for logs)

---

## Future Enhancements

### Short-term (v1.1)

1. **Authentication & Authorization**:
   - JWT tokens
   - API keys
   - RBAC

2. **Rate Limiting**:
   - Per-user quotas
   - Burst handling

3. **Batch Endpoint**:
   ```python
   @app.post("/verify/batch")
   async def verify_batch(requests: List[VerificationRequest]):
       # Process in parallel
   ```

4. **Async Database**:
   - Migrate to `asyncpg`
   - Non-blocking queries

### Medium-term (v2.0)

1. **Fine-tuned Embeddings**:
   - Domain-specific embedding model (legal text)
   - Fine-tune E5-large on legal corpus

2. **Explanation Generation**:
   - LLM-based explanations for rejections
   - "This claim was rejected because..."

3. **Active Learning**:
   - Collect edge cases
   - Retrain/fine-tune models

4. **Multi-language Support**:
   - English, French legal domains
   - Pluggable language modules

### Long-term (v3.0)

1. **Ensemble Models**:
   - Combine multiple embeddings (E5, SBERT, custom)
   - Voting or weighted averaging

2. **Real-time Streaming**:
   - WebSocket API for live verification
   - Server-Sent Events (SSE)

3. **GraphQL API**:
   - More flexible queries
   - Client-driven field selection

4. **Federated Learning**:
   - Improve models without centralizing data
   - Privacy-preserving training

---

## References

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [spaCy Documentation](https://spacy.io/)
- [sentence-transformers Documentation](https://www.sbert.net/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [Prometheus Documentation](https://prometheus.io/docs/)
- [Grafana Documentation](https://grafana.com/docs/)

---

**Built with ❤️ by the JuraGPT Team**
