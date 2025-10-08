# 🏛️ System Architecture

**For AI Agents**: This document explains the complete system design, component relationships, and data flow.

---

## 📐 Design Philosophy

This system follows **separation of concerns** with three distinct layers:

1. **Data Layer** (`corpus/`) - Isolated knowledge base
2. **Logic Layer** (`app/`) - Application code
3. **Infrastructure Layer** (Docker, config) - Deployment

### Key Principles

- **Determinism**: Temperature=0, fixed prompts, reproducible outputs
- **Security-first**: RBAC enforced before LLM sees data
- **Corpus isolation**: Knowledge completely separated from code
- **Portability**: Zero cloud dependencies, runs anywhere

---

## 🧩 Component Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         FastAPI App                          │
│                        (app/main.py)                         │
└────────────────────────┬────────────────────────────────────┘
                         │
           ┌─────────────┼─────────────┐
           │             │             │
           ▼             ▼             ▼
    ┌──────────┐  ┌──────────┐  ┌──────────┐
    │ Security │  │Retrieval │  │Generation│
    │ (RBAC)   │  │ (RAG)    │  │ (LLM)    │
    └────┬─────┘  └────┬─────┘  └────┬─────┘
         │             │              │
         │             ▼              │
         │      ┌────────────┐        │
         │      │ VectorStore│        │
         │      │  (Chroma)  │        │
         │      └────────────┘        │
         │                            │
         ▼                            ▼
    ┌─────────────┐          ┌──────────────┐
    │privilege_map│          │ Ollama/LLM   │
    │   .json     │          │  (External)  │
    └─────────────┘          └──────────────┘
         │
         ▼
    ┌──────────┐
    │  corpus/ │
    │  (Data)  │
    └──────────┘
```

---

## 📦 Module Responsibilities

### `app/config.py`
**Purpose**: Centralized configuration management

**Responsibilities**:
- Load environment variables
- Define paths (all relative to PROJECT_ROOT)
- Validate configuration on startup
- Provide configuration constants

**Key Functions**:
- `validate_config()` - Check critical paths exist
- `load_privilege_map()` - Load RBAC from corpus

**Dependencies**: Standard library only

---

### `app/models.py`
**Purpose**: API contracts and data validation

**Responsibilities**:
- Define request/response schemas
- Validate input data
- Normalize data (lowercase tags, trim strings)

**Key Models**:
- `AskQuestion` - User query request
- `Answer` - Response with grounding metadata
- `UpsertDocument` - Document insertion
- `HealthCheck` - System status

**Dependencies**: Pydantic

---

### `app/security.py`
**Purpose**: RBAC policy enforcement

**Responsibilities**:
- Load and manage privilege map
- Check document access permissions
- Generate policy audit hashes
- Validate scopes

**Key Functions**:
- `scope_allowed(scope, doc_tags) -> bool` - Core RBAC check
- `get_policy_hash(scope) -> str` - Audit trail hash
- `reload_policies()` - Hot-reload without restart

**Algorithm**:
```python
# Document is allowed if:
has_allowed_tag = (doc_tags ∩ allowed_tags) ≠ ∅
has_no_denied_tag = (doc_tags ∩ deny_tags) = ∅
allowed = has_allowed_tag AND has_no_denied_tag
```

**Dependencies**: Standard library only

---

### `app/retrieval.py`
**Purpose**: Vector store and embedding management

**Responsibilities**:
- Initialize ChromaDB collection
- Embed and store documents
- Query for similar documents
- Convert distance to similarity

**Key Functions**:
- `upsert(doc_id, text, tags, metadata)` - Add/update document
- `query(query_text, n_results) -> (docs, metas, dists)` - Retrieve similar
- `distance_to_similarity(distance) -> float` - Convert L2 to similarity

**Similarity Conversion**:
```python
similarity = 1.0 / (1.0 + L2_distance)
# Maps: distance [0, ∞) → similarity [1, 0)
```

**Optimization**: LRU cache for frequent queries

**Dependencies**: ChromaDB, sentence-transformers

---

### `app/generation.py`
**Purpose**: LLM prompt construction and generation

**Responsibilities**:
- Build deterministic prompts
- Call Ollama API with fixed parameters
- Normalize LLM outputs
- Detect refusals

**Key Functions**:
- `build_prompt(question, context, scope, policy_hash) -> str` - Construct prompt
- `generate_answer(prompt) -> str` - Call LLM via HTTP
- `is_refusal(answer) -> bool` - Detect non-answers
- `answer_question(...) -> (answer, is_refusal)` - High-level orchestration

**Prompt Structure**:
```
1. System instructions (grounding rules)
2. RBAC scope + policy hash (audit)
3. Context chunks (retrieved docs)
4. User question
5. Output directive
```

**Determinism Settings**:
- `temperature: 0.0` - No randomness
- `top_k: 1` - Greedy decoding
- `top_p: 1.0` - No nucleus sampling

**Dependencies**: httpx, standard library

---

### `app/main.py`
**Purpose**: FastAPI application and HTTP endpoints

**Responsibilities**:
- Define API routes
- Orchestrate components
- Handle HTTP errors
- Lifecycle management (startup/shutdown)

**Endpoints**:

| Method | Path                  | Purpose                          |
|--------|-----------------------|----------------------------------|
| GET    | `/health`             | Health check                     |
| POST   | `/upsert`             | Add single document              |
| POST   | `/batch_upsert`       | Add multiple documents           |
| POST   | `/ask`                | Ask question (main endpoint)     |
| DELETE | `/document/{id}`      | Remove document                  |
| GET    | `/corpus/stats`       | Get corpus statistics            |
| POST   | `/security/reload`    | Reload RBAC policies             |

**Request Flow** (`/ask` endpoint):
```
1. Validate scope exists
2. Query vector store for TOP_K similar docs
3. Filter by similarity threshold (≥0.75)
4. Filter by RBAC (scope_allowed check)
5. If no docs pass → return refusal
6. Build prompt with filtered context
7. Call LLM with deterministic params
8. Check if answer is refusal
9. Return answer + metadata
```

**Dependencies**: FastAPI, all app modules

---

## 🔄 Data Flow

### Question Answering Flow

```
User Question
    ↓
[1] API Request (/ask)
    ↓
[2] Validate Scope (security.py)
    ↓
[3] Embed Question (retrieval.py)
    ↓
[4] Vector Search (ChromaDB)
    ↓
[5] Retrieve TOP_K Candidates
    ↓
[6] Filter by Similarity (≥ threshold)
    ↓
[7] Filter by RBAC (scope_allowed)
    ↓
[8] Build Prompt (generation.py)
    ↓
[9] Generate Answer (Ollama API)
    ↓
[10] Normalize + Detect Refusal
    ↓
[11] Return Answer + Metadata
```

### Document Ingestion Flow

```
Document Content
    ↓
[1] API Request (/upsert or /batch_upsert)
    ↓
[2] Validate with Pydantic (models.py)
    ↓
[3] Normalize Tags (lowercase, trim)
    ↓
[4] Embed Document (retrieval.py)
    ↓
[5] Store in ChromaDB
    ↓
[6] Return Success
```

---

## 🔐 Security Model

### Defense in Depth

1. **Input Validation**: Pydantic schemas reject malformed data
2. **RBAC Pre-filtering**: Unauthorized docs never reach LLM
3. **Similarity Threshold**: Low-quality matches rejected
4. **Prompt Guardrails**: Instructions prevent prompt injection
5. **Output Validation**: Refusal detection catches model drift

### RBAC Enforcement Point

**Critical**: RBAC is enforced **before** LLM generation, not after.

```python
# BAD (post-generation filtering)
answer = llm.generate(question)
if not allowed(answer):
    return refusal

# GOOD (pre-generation filtering)
context = retrieve(question)
context = filter_by_rbac(context, scope)  # ← Enforcement point
answer = llm.generate(question, context)
```

### Policy Hash

Every prompt includes a `SCOPE_POLICY_HASH` for audit trails:

```python
policy_hash = sha256(json.dumps(scope_policy, sort_keys=True))[:8]
```

This allows detecting policy tampering in logged prompts.

---

## 🗄️ Data Storage

### Vector Store (ChromaDB)

**Location**: `.chroma/` (configurable via `CHROMA_PERSIST_DIR`)

**Schema**:
- **ids**: Document unique identifiers
- **documents**: Text content (embedded automatically)
- **metadatas**: `{"tags": [...], ...}`
- **embeddings**: Generated by sentence-transformers

**Persistence**: Disk-backed, survives restarts

### Corpus (File System)

**Location**: `corpus/`

**Structure**:
```
corpus/
├── privilege_map.json   # RBAC definitions (required)
├── metadata.json        # Version tracking (required)
└── docs/                # Markdown files (source of truth)
```

**Sync**: Use `scripts/seed_corpus.py` to sync `corpus/docs/` → ChromaDB

---

## 🚀 Deployment Patterns

### Standalone (Development)
```bash
python -m uvicorn app.main:app --reload
```

### Docker (Production)
```bash
docker-compose up
```

### With Shared Corpus
```yaml
# Multiple bot instances sharing corpus
services:
  bot-1:
    volumes:
      - /shared/corpus:/app/corpus:ro
  bot-2:
    volumes:
      - /shared/corpus:/app/corpus:ro
```

---

## 🧪 Testing Strategy

### Unit Tests
- `test_security.py`: RBAC logic
- `test_retrieval.py`: Vector operations
- `test_models.py`: Validation

### Integration Tests
- End-to-end `/ask` flow
- Document ingestion
- Refusal cases

---

## 🔧 Extending the System

### Adding New RBAC Scope

1. Edit `corpus/privilege_map.json`
2. Call `POST /security/reload` (or restart)
3. Test with new scope in `/ask` requests

### Swapping Vector Store (Chroma → Qdrant)

1. Implement new class in `app/retrieval.py`:
   ```python
   class QdrantVectorStore:
       def upsert(...): ...
       def query(...): ...
   ```
2. Update `get_vector_store()` factory
3. Update `config.py` with Qdrant settings

### Changing LLM Backend

1. Update `app/generation.py`:
   - Modify `generate_answer()` to call new API
   - Keep same parameters (temperature, top_k, etc.)
2. Update `config.py` endpoint settings

---

## 📊 Performance Characteristics

### Latency Targets
- **Health check**: <10ms
- **Document upsert**: <100ms
- **Question answering**: <2s (depends on LLM)

### Resource Usage
- **Memory**: ~100MB base + model size
- **Disk**: ~50MB + corpus embeddings
- **CPU**: Minimal (I/O bound)

### Bottlenecks
1. **LLM generation**: Slowest component (GPU helps)
2. **Embedding**: Cached queries help
3. **Vector search**: Scales to 100K+ docs with HNSW

---

## 🐛 Debugging

### Common Issues

**Q**: Bot refuses to answer valid questions
**A**: Check similarity threshold, verify document tags match scope

**Q**: Wrong answers given
**A**: Check retrieved context quality, review TOP_K setting

**Q**: Slow responses
**A**: Profile LLM endpoint, check network latency, enable query cache

### Logging

Enable debug logging:
```bash
export LOG_LEVEL=DEBUG
```

Key log points:
- Retrieved document count
- Filtered document count (post-RBAC)
- Policy hash used
- LLM endpoint response time

---

## 🎯 For AI Agents

When modifying this system:

1. **Preserve determinism**: Never change temperature or sampling params
2. **Maintain RBAC**: All new features must respect scope filtering
3. **Document changes**: Update this file if architecture changes
4. **Test isolation**: Ensure corpus remains isolated from app code
5. **Validate configs**: Run `validate_config()` after changes

**Critical paths** to preserve:
- `corpus/` directory structure
- RBAC enforcement in `/ask` flow
- Prompt template in `generation.py`
