# 🎯 Implementation Plan (Reality-Based)
## Chatbot FAQ Agent - Practical Transformation Strategy

**Version:** 1.0
**Created:** 2025-10-08
**Status:** Planning
**Approach:** Evidence-Based, Staged Implementation

---

## 📊 Reality Check: Analysis vs. Actual Codebase

### What the Reports Said vs. What Actually Exists

#### ✅ CONFIRMED CRITICAL BUGS

| Bug | Report Location | Actual Code Location | Severity |
|-----|----------------|---------------------|----------|
| **Hardcoded threshold** | `main.py:167` | ✅ `main.py:167` - `if similarity >= 0.75` | 🔴 CRITICAL |
| **Wrong distance formula** | `retrieval.py:159` | ✅ `retrieval.py:146-159` - L2 formula for cosine | 🔴 CRITICAL |
| **Unused cache** | `main.py:159` | ✅ `cached_query()` exists but never called | 🟠 HIGH |
| **No max_length** | `models.py:30,14` | ✅ No `max_length` on any text fields | 🟠 HIGH |

**Verdict:** All reported bugs are CONFIRMED. The analysis was accurate.

---

#### ✅ CONFIRMED ARCHITECTURE ISSUES

| Issue | Analysis Finding | Actual Reality | Impact |
|-------|-----------------|----------------|--------|
| **Tight coupling to ChromaDB** | High coupling | ✅ Direct `chromadb` imports in `retrieval.py` | 🔴 HIGH |
| **Tight coupling to Ollama** | High coupling | ✅ Hardcoded httpx POST to Ollama endpoint | 🔴 HIGH |
| **No abstractions** | Missing protocols | ✅ No `protocols.py`, no interfaces | 🔴 HIGH |
| **No authentication** | Missing auth | ✅ No authentication anywhere | 🟠 HIGH |
| **No rate limiting** | Missing rate limits | ✅ No rate limiting | 🟠 HIGH |
| **CORS wildcard** | `*` in config | ✅ `CORS_ORIGINS = "*"` in `.env.example` | 🟠 MEDIUM |
| **No input sanitization** | Missing validation | ✅ No sanitization functions | 🟠 MEDIUM |

**Verdict:** All architectural issues confirmed. No abstractions exist.

---

#### ✅ WHAT ACTUALLY WORKS WELL

**Positive Findings:**

1. **Clean Code Structure** ✅
   - Well-organized modules (`main.py`, `config.py`, `retrieval.py`, `generation.py`, `security.py`)
   - Good separation of concerns
   - Singleton pattern correctly used
   - Type hints present

2. **RBAC System** ✅
   - `security.py` is well-implemented
   - `privilege_map.json` system works
   - Tag-based filtering logic is solid
   - Policy hashing for audit trails

3. **Configuration System** ✅
   - Centralized in `config.py`
   - Environment variable support
   - Path resolution works correctly
   - Validation function exists

4. **API Design** ✅
   - FastAPI with Pydantic models
   - Clear endpoint structure
   - Health check endpoint
   - Batch operations support

5. **Corpus Structure** ✅
   - Isolated in `corpus/` directory
   - Markdown-based docs
   - Metadata tracking
   - Tag system

**Key Insight:** The foundation is solid. We need to:
- Fix critical bugs FIRST
- Layer abstractions ON TOP of existing code
- Gradually migrate without breaking what works

---

## 🎯 Staged Implementation Strategy

### Design Principles

1. **Non-Breaking Changes:** Preserve existing functionality throughout
2. **Incremental Value:** Each stage delivers working improvements
3. **Backward Compatible:** Old code paths work until deprecated
4. **Evidence-Based:** Fix confirmed bugs before theoretical improvements
5. **Practical Focus:** Prioritize production-readiness over perfect architecture

---

## 🚨 STAGE 0: Emergency Bug Fixes (Immediate)
**Goal:** Fix broken functionality that prevents correct operation
**Status:** Must complete before any other work

### Critical Bugs (Fix Order)

#### Bug 1: Hardcoded Similarity Threshold
**File:** `app/main.py:167`

**Current (BROKEN):**
```python
if similarity >= 0.75 and security.scope_allowed(q.scope, doc_tags):
```

**Fix:**
```python
from app.config import SIMILARITY_THRESHOLD

# Line 167
if similarity >= SIMILARITY_THRESHOLD and security.scope_allowed(q.scope, doc_tags):
```

**Steps:**
1. Add import at top of `main.py`
2. Replace hardcoded value
3. Test with different threshold values
4. Verify config changes are respected

---

#### Bug 2: Distance Metric Formula
**File:** `app/retrieval.py:146-159`

**Current (WRONG):**
```python
@staticmethod
def distance_to_similarity(distance: float) -> float:
    """Convert Chroma distance to similarity score."""
    # BUG: This is L2 formula, but Chroma uses cosine!
    return 1.0 / (1.0 + distance)
```

**Fix:**
```python
@staticmethod
def distance_to_similarity(distance: float) -> float:
    """
    Convert Chroma cosine distance to similarity score.

    ChromaDB cosine distance range: [0, 2]
    - 0 = identical vectors (similarity = 1.0)
    - 2 = opposite vectors (similarity = 0.0)

    Formula: similarity = 1.0 - (distance / 2.0)
    Maps [0, 2] → [1.0, 0.0]
    """
    # Correct formula for cosine distance
    return 1.0 - (distance / 2.0)
```

**Alternative (Config-Driven):**
```python
from app.config import DISTANCE_METRIC  # Add to config.py

@staticmethod
def distance_to_similarity(distance: float, metric: str = "cosine") -> float:
    """Convert distance to similarity based on metric type."""
    if metric == "cosine":
        # Cosine: [0, 2] → [1.0, 0.0]
        return 1.0 - (distance / 2.0)
    elif metric == "l2":
        # L2: [0, ∞) → [1.0, 0.0)
        return 1.0 / (1.0 + distance)
    elif metric == "ip":
        # Inner product (already similarity-like)
        return distance
    else:
        raise ValueError(f"Unknown distance metric: {metric}")
```

**Steps:**
1. Update formula in `retrieval.py`
2. Add `DISTANCE_METRIC = "cosine"` to `config.py`
3. Update call site in `main.py:164`
4. Add unit tests with known examples
5. Verify similarity scores make sense

---

#### Bug 3: Enable Cached Query
**File:** `app/main.py:159`

**Current (UNUSED):**
```python
# Line 159 - directly calls store.query()
documents, metadatas, distances = store.query(q.question)

# Line 174-190 in retrieval.py - function exists but never called
@lru_cache(maxsize=EMBEDDING_CACHE_SIZE)
def cached_query(query_text: str, n_results: int = TOP_K) -> str:
    ...
```

**Problem:** Function returns JSON string (not ideal for caching)

**Fix Option 1 (Quick):**
```python
# In main.py:159
from app.retrieval import cached_query
import json

result_json = cached_query(q.question, n_results=TOP_K)
result = json.loads(result_json)
documents = result["documents"]
metadatas = result["metadatas"]
distances = result["distances"]
```

**Fix Option 2 (Better - Refactor):**
```python
# In retrieval.py - make cache return tuple
from functools import lru_cache
from typing import Tuple, List, Dict, Any

@lru_cache(maxsize=EMBEDDING_CACHE_SIZE)
def _get_query_key(query_text: str, n_results: int) -> str:
    """Generate cache key."""
    return f"{query_text}|{n_results}"

def cached_query(
    query_text: str,
    n_results: int = TOP_K
) -> Tuple[List[str], List[Dict[str, Any]], List[float]]:
    """
    Query with caching for frequently asked questions.
    Uses query text + n_results as cache key.
    """
    cache_key = _get_query_key(query_text, n_results)

    # Check if we've seen this query before
    if cache_key in _query_cache:
        return _query_cache[cache_key]

    # Not in cache - query vector store
    store = get_vector_store()
    result = store.query(query_text, n_results)

    # Store in cache
    _query_cache[cache_key] = result

    return result

# Global cache (LRU)
_query_cache: Dict[str, Tuple] = {}
```

**Steps:**
1. Choose fix approach (Option 1 for quick, Option 2 for clean)
2. Update `main.py` to use cached version
3. Add cache invalidation on corpus updates
4. Test cache hit rate
5. Measure performance improvement

---

#### Bug 4: Add Input Length Limits
**File:** `app/models.py:14, 30`

**Current (VULNERABLE):**
```python
class UpsertDocument(BaseModel):
    text: str = Field(..., min_length=1, description="Document content")
    # No max_length - can upload gigabytes!

class AskQuestion(BaseModel):
    question: str = Field(..., min_length=1, description="User's question")
    # No max_length - DoS vulnerability!
```

**Fix:**
```python
# Add to config.py first
MAX_QUESTION_LENGTH = int(os.getenv("MAX_QUESTION_LENGTH", "500"))
MAX_DOCUMENT_LENGTH = int(os.getenv("MAX_DOCUMENT_LENGTH", "10000"))

# Update models.py
from app.config import MAX_QUESTION_LENGTH, MAX_DOCUMENT_LENGTH

class UpsertDocument(BaseModel):
    text: str = Field(
        ...,
        min_length=1,
        max_length=MAX_DOCUMENT_LENGTH,
        description="Document content (max 10KB)"
    )

class AskQuestion(BaseModel):
    question: str = Field(
        ...,
        min_length=1,
        max_length=MAX_QUESTION_LENGTH,
        description="User's question (max 500 chars)"
    )
```

**Steps:**
1. Add config variables
2. Update Pydantic models
3. Test with oversized inputs
4. Verify error messages are helpful
5. Document limits in API docs

---

### Stage 0 Validation

**Definition of Done:**
- [ ] All 4 bugs fixed
- [ ] Configuration system works correctly
- [ ] Similarity calculations are mathematically correct
- [ ] Cache is being used and provides speedup
- [ ] Input validation prevents oversized inputs
- [ ] All existing tests still pass
- [ ] New tests added for each fix
- [ ] Documented in changelog

**Deliverables:**
- ✅ Working configuration system
- ✅ Correct similarity calculations
- ✅ Active caching layer
- ✅ Input protection
- ✅ Test coverage for fixes

---

## 🔐 STAGE 1: Security Hardening (High Priority)
**Goal:** Make system production-safe with authentication and protection
**Prerequisites:** Stage 0 complete

### 1.1: Authentication System

**Create:** `app/auth.py`

**Implementation:**
```python
"""
Authentication and authorization middleware.
Supports JWT tokens and API keys.
"""

from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
import jwt
import secrets
from datetime import datetime, timedelta

# Security scheme
security_scheme = HTTPBearer()

# In-memory API keys (for MVP - move to database later)
API_KEYS: dict[str, dict] = {
    # "key": {"user_id": "user", "scopes": ["public", "support"]}
}

def generate_api_key() -> str:
    """Generate a secure API key."""
    return secrets.token_urlsafe(32)

def validate_api_key(key: str) -> Optional[dict]:
    """Validate API key and return user info."""
    return API_KEYS.get(key)

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security_scheme)
) -> dict:
    """
    Dependency to extract and validate current user from token/key.

    Raises:
        HTTPException: 401 if invalid credentials
    """
    token = credentials.credentials

    # Try API key first
    user_info = validate_api_key(token)
    if user_info:
        return user_info

    # Try JWT token (future implementation)
    # For now, reject
    raise HTTPException(
        status_code=401,
        detail="Invalid authentication credentials"
    )

def require_scope(required_scope: str):
    """Dependency to check if user has required scope."""
    def scope_checker(user: dict = Depends(get_current_user)) -> dict:
        user_scopes = user.get("scopes", [])
        if required_scope not in user_scopes:
            raise HTTPException(
                status_code=403,
                detail=f"Scope '{required_scope}' required"
            )
        return user
    return scope_checker
```

**Update:** `app/main.py`

```python
from app.auth import get_current_user, require_scope

# Make authentication optional at first (gradual rollout)
REQUIRE_AUTH = os.getenv("REQUIRE_AUTH", "false").lower() == "true"

@app.post("/ask", response_model=Answer)
async def ask_question(
    q: AskQuestion,
    user: dict = Depends(get_current_user) if REQUIRE_AUTH else None
):
    """Ask a question with optional authentication."""

    # If auth is enabled, verify user can access requested scope
    if REQUIRE_AUTH and user:
        user_scopes = user.get("scopes", [])
        if q.scope not in user_scopes:
            raise HTTPException(
                status_code=403,
                detail=f"User does not have access to scope '{q.scope}'"
            )

    # Rest of existing code...
```

**Steps:**
1. Create `auth.py` with API key validation
2. Add authentication dependencies
3. Make auth optional via config flag
4. Create admin endpoint for key management
5. Test with valid and invalid keys
6. Document authentication setup

---

### 1.2: Rate Limiting

**Install dependency:**
```txt
# Add to requirements.txt
slowapi==0.1.9
```

**Implement:**
```python
# In app/main.py
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

# Create limiter
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["100/hour"]  # Global limit
)

# Add to app
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Apply to endpoints
@app.post("/ask", response_model=Answer)
@limiter.limit("10/minute")  # 10 questions per minute per IP
async def ask_question(request: Request, q: AskQuestion):
    ...

@app.post("/upsert")
@limiter.limit("20/minute")  # 20 upserts per minute per IP
def upsert_document(request: Request, doc: UpsertDocument):
    ...
```

**Steps:**
1. Install slowapi
2. Configure limiter
3. Apply to sensitive endpoints
4. Test rate limit enforcement
5. Add rate limit headers
6. Document limits

---

### 1.3: Input Sanitization & Prompt Injection Defense

**Create:** `app/security/input_validation.py`

```python
"""
Input sanitization and prompt injection protection.
"""

import re
from typing import List

# Suspicious patterns that might indicate injection attempts
INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"ignore\s+(all\s+)?above",
    r"you\s+are\s+now",
    r"new\s+instructions?:",
    r"system\s*:",
    r"assistant\s*:",
    r"<\|system\|>",
    r"<\|assistant\|>",
    r"forget\s+(the\s+)?context",
    r"disregard\s+(the\s+)?rules",
]

COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in INJECTION_PATTERNS]

def detect_injection_attempt(text: str) -> tuple[bool, str | None]:
    """
    Detect potential prompt injection attempts.

    Returns:
        (is_suspicious, reason)
    """
    text_lower = text.lower()

    for pattern in COMPILED_PATTERNS:
        if pattern.search(text_lower):
            return True, f"Suspicious pattern detected: {pattern.pattern}"

    return False, None

def sanitize_input(text: str) -> str:
    """
    Sanitize user input.

    - Remove control characters
    - Normalize whitespace
    - Trim to reasonable length
    """
    # Remove control characters
    text = "".join(char for char in text if ord(char) >= 32 or char in '\n\t')

    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text)

    # Trim
    text = text.strip()

    return text

def validate_question(question: str) -> str:
    """
    Validate and sanitize a question.

    Raises:
        ValueError: If question is suspicious
    """
    # Sanitize first
    clean_question = sanitize_input(question)

    # Check for injection
    is_suspicious, reason = detect_injection_attempt(clean_question)
    if is_suspicious:
        raise ValueError(f"Invalid question: {reason}")

    return clean_question
```

**Update:** `app/main.py`

```python
from app.security.input_validation import validate_question

@app.post("/ask", response_model=Answer)
async def ask_question(q: AskQuestion, ...):
    # Validate and sanitize question
    try:
        clean_question = validate_question(q.question)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Use clean_question instead of q.question
    documents, metadatas, distances = store.query(clean_question)
    ...
```

**Steps:**
1. Create validation module
2. Implement pattern detection
3. Add sanitization functions
4. Integrate into ask endpoint
5. Test with injection attempts
6. Log blocked attempts

---

### 1.4: Audit Logging

**Create:** `app/audit.py`

```python
"""
Comprehensive audit logging for compliance and security.
"""

import logging
import json
from datetime import datetime
from typing import Optional

# Set up structured logger
audit_logger = logging.getLogger("audit")
audit_logger.setLevel(logging.INFO)

# JSON formatter for structured logs
class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "event": record.msg,
            "data": record.__dict__.get("data", {})
        }
        return json.dumps(log_data)

# Configure handler
handler = logging.FileHandler("logs/audit.log")
handler.setFormatter(JSONFormatter())
audit_logger.addHandler(handler)

def log_query(
    user_id: str,
    scope: str,
    question: str,
    retrieved: int,
    filtered: int,
    is_refusal: bool,
    latency_ms: float,
    policy_hash: str
):
    """Log a query event."""
    audit_logger.info("query", extra={
        "data": {
            "user_id": user_id,
            "scope": scope,
            "question": question[:100],  # Truncate
            "retrieved": retrieved,
            "filtered": filtered,
            "is_refusal": is_refusal,
            "latency_ms": latency_ms,
            "policy_hash": policy_hash
        }
    })

def log_auth_failure(user_id: str, reason: str):
    """Log authentication failure."""
    audit_logger.warning("auth_failure", extra={
        "data": {"user_id": user_id, "reason": reason}
    })

def log_rate_limit(user_id: str, endpoint: str):
    """Log rate limit hit."""
    audit_logger.warning("rate_limit", extra={
        "data": {"user_id": user_id, "endpoint": endpoint}
    })
```

**Update:** `app/main.py`

```python
from app.audit import log_query
import time

@app.post("/ask", response_model=Answer)
async def ask_question(q: AskQuestion, ...):
    start_time = time.time()

    # ... existing code ...

    # Log query
    latency_ms = (time.time() - start_time) * 1000
    log_query(
        user_id=q.user_id,
        scope=q.scope,
        question=q.question,
        retrieved=len(documents),
        filtered=len(context_chunks),
        is_refusal=is_refusal,
        latency_ms=latency_ms,
        policy_hash=policy_hash
    )

    return Answer(...)
```

**Steps:**
1. Create audit module
2. Set up structured logging
3. Add logging to all critical operations
4. Create log rotation strategy
5. Test log output
6. Document log format

---

### 1.5: CORS Configuration Hardening

**Update:** `.env.example` and `app/config.py`

```bash
# OLD (Insecure)
CORS_ORIGINS=*

# NEW (Secure)
CORS_ORIGINS=https://yourdomain.com,https://app.yourdomain.com
```

```python
# In config.py - Add validation
def validate_cors_origins():
    """Warn if CORS is set to wildcard."""
    if "*" in CORS_ORIGINS:
        print("⚠️  WARNING: CORS is set to wildcard (*)")
        print("   This allows ANY website to call your API")
        print("   Set CORS_ORIGINS to specific domains for production")
```

**Steps:**
1. Update default config
2. Add validation warning
3. Document CORS setup
4. Test with real origins

---

### Stage 1 Validation

**Definition of Done:**
- [ ] Authentication system works (API keys)
- [ ] Rate limiting blocks excessive requests
- [ ] Prompt injection patterns are detected
- [ ] Audit logs capture all events
- [ ] CORS is configurable
- [ ] Security tests pass
- [ ] Documentation updated

**Deliverables:**
- ✅ Working authentication system
- ✅ Rate limiting on all endpoints
- ✅ Input validation and sanitization
- ✅ Comprehensive audit logging
- ✅ Hardened CORS configuration
- ✅ Security documentation

---

## 🏗️ STAGE 2: Abstraction Layer Foundation
**Goal:** Create protocol-based architecture without breaking existing code
**Prerequisites:** Stage 0, Stage 1 complete

### 2.1: Define Core Protocols

**Create:** `app/protocols.py`

**Strategy:** Define protocols that EXISTING code already satisfies

```python
"""
Core abstractions for the FAQ chatbot.

These protocols define interfaces that components must satisfy.
Existing implementations already satisfy these protocols without modification.
"""

from typing import Protocol, List, Dict, Any, Tuple, Optional
from dataclasses import dataclass

# ==================== Data Models ====================

@dataclass
class Embedding:
    """Vector representation of text."""
    vector: List[float]
    model: str
    dimension: int

@dataclass
class SearchResult:
    """Result from vector search."""
    id: str
    content: str
    score: float  # 0.0-1.0, higher = better
    metadata: Dict[str, Any]
    distance: Optional[float] = None

@dataclass
class GenerationConfig:
    """LLM generation configuration."""
    temperature: float = 0.0
    max_tokens: int = 384
    top_p: float = 1.0
    top_k: int = 1

    def is_deterministic(self) -> bool:
        return self.temperature == 0.0 and self.top_k == 1

# ==================== Protocols ====================

class VectorStore(Protocol):
    """
    Interface for vector storage and retrieval.

    Current implementation: ChromaDB (retrieval.VectorStore)
    Already satisfies this protocol!
    """

    def upsert(
        self,
        doc_id: str,
        text: str,
        tags: List[str],
        metadata: Dict[str, Any] | None = None
    ) -> None:
        """Insert or update a document."""
        ...

    def query(
        self,
        query_text: str,
        n_results: int = 4
    ) -> Tuple[List[str], List[Dict[str, Any]], List[float]]:
        """Search for similar documents."""
        ...

    def delete(self, doc_id: str) -> None:
        """Delete a document by ID."""
        ...

    def count(self) -> int:
        """Total document count."""
        ...

class LLMProvider(Protocol):
    """
    Interface for LLM generation.

    Will be satisfied by adapters (Ollama, OpenAI, etc.)
    """

    async def generate(
        self,
        prompt: str,
        config: GenerationConfig
    ) -> str:
        """Generate text from prompt."""
        ...

class SecurityPolicy(Protocol):
    """
    Interface for access control.

    Current implementation: security.SecurityPolicy
    Already satisfies this protocol!
    """

    def scope_allowed(self, scope: str, doc_tags: List[str]) -> bool:
        """Check if scope can access document."""
        ...

    def validate_scope(self, scope: str) -> bool:
        """Check if scope exists."""
        ...

    def get_policy_hash(self, scope: str) -> str:
        """Get policy hash for audit."""
        ...
```

**Key Insight:** Our existing classes (`VectorStore`, `SecurityPolicy`) already satisfy these protocols! No code changes needed - we're just documenting the interface.

---

### 2.2: Create Adapter for Ollama

**Create:** `app/adapters/__init__.py`
**Create:** `app/adapters/llm/__init__.py`
**Create:** `app/adapters/llm/ollama.py`

```python
"""
Ollama LLM adapter.
Wraps existing generation.py functions into protocol-compliant adapter.
"""

import httpx
from typing import Optional
from app.protocols import LLMProvider, GenerationConfig
from app.config import MODEL_ENDPOINT, MODEL_NAME

class OllamaLLM:
    """
    Ollama implementation of LLMProvider protocol.

    Wraps existing generation logic from app.generation module.
    """

    def __init__(self, endpoint: str = MODEL_ENDPOINT, model: str = MODEL_NAME):
        self.endpoint = endpoint
        self.model = model

    @property
    def model_name(self) -> str:
        return self.model

    async def generate(self, prompt: str, config: GenerationConfig) -> str:
        """Generate text using Ollama."""
        # Use existing generation logic
        from app.generation import generate_answer

        # Temporarily override config (for now)
        # TODO: Refactor generate_answer to accept config parameter
        answer = await generate_answer(prompt)
        return answer

    async def health_check(self) -> bool:
        """Check if Ollama is available."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.endpoint}/api/tags")
                return response.status_code == 200
        except Exception:
            return False
```

**Steps:**
1. Create adapter directory structure
2. Implement Ollama adapter
3. Ensure it satisfies `LLMProvider` protocol
4. Test adapter independently
5. Document adapter

---

### 2.3: Create Plugin Registry (Basic)

**Create:** `app/registry.py`

```python
"""
Simple plugin registry for discovering and creating providers.
"""

from typing import Dict, Any, Callable, Type
from app.protocols import LLMProvider, VectorStore, SecurityPolicy

# Registry storage
_llm_providers: Dict[str, Type[LLMProvider]] = {}
_vector_stores: Dict[str, Type[VectorStore]] = {}

# ==================== Registration Decorators ====================

def llm_provider(name: str):
    """Decorator to register an LLM provider."""
    def decorator(cls):
        _llm_providers[name] = cls
        return cls
    return decorator

def vector_store_provider(name: str):
    """Decorator to register a vector store provider."""
    def decorator(cls):
        _vector_stores[name] = cls
        return cls
    return decorator

# ==================== Factory Functions ====================

def create_llm(provider: str, config: Dict[str, Any]) -> LLMProvider:
    """
    Create LLM provider instance.

    Args:
        provider: Provider name (e.g., "ollama", "openai")
        config: Provider-specific configuration

    Returns:
        LLMProvider instance

    Raises:
        ValueError: If provider unknown
    """
    if provider not in _llm_providers:
        available = ", ".join(_llm_providers.keys())
        raise ValueError(
            f"Unknown LLM provider: '{provider}'\n"
            f"Available: {available}\n"
            f"See docs/plugins.md for adding new providers"
        )

    provider_class = _llm_providers[provider]
    return provider_class(**config)

def list_llm_providers() -> list[str]:
    """List all registered LLM providers."""
    return list(_llm_providers.keys())

# ==================== Auto-register Built-in Providers ====================

# Auto-import and register built-in providers
def _register_builtin():
    """Register built-in providers on import."""
    try:
        from app.adapters.llm.ollama import OllamaLLM
        llm_provider("ollama")(OllamaLLM)
    except ImportError:
        pass

_register_builtin()
```

**Steps:**
1. Create registry module
2. Implement registration decorators
3. Implement factory functions
4. Auto-register Ollama adapter
5. Test registry operations

---

### 2.4: Configuration Enhancement (YAML Support)

**Install:**
```txt
# Add to requirements.txt
pyyaml==6.0.1
pydantic-settings==2.1.0
```

**Create:** `app/config_loader.py`

```python
"""
Enhanced configuration system with YAML support.
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any

def load_yaml_config(config_path: str | Path) -> Dict[str, Any]:
    """Load configuration from YAML file."""
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    # Interpolate environment variables
    config = _interpolate_env_vars(config)

    return config

def _interpolate_env_vars(config: Any) -> Any:
    """
    Recursively replace ${VAR_NAME} with environment variables.

    Example:
        api_key: ${OPENAI_API_KEY}  →  api_key: sk-...
    """
    if isinstance(config, dict):
        return {k: _interpolate_env_vars(v) for k, v in config.items()}
    elif isinstance(config, list):
        return [_interpolate_env_vars(item) for item in config]
    elif isinstance(config, str) and config.startswith("${") and config.endswith("}"):
        var_name = config[2:-1]
        return os.getenv(var_name, config)  # Fallback to original if not found
    else:
        return config
```

**Create:** `config/local.yaml` (example)

```yaml
# Local development configuration

providers:
  llm:
    provider: ollama
    config:
      endpoint: http://localhost:11434
      model: qwen2.5:3b-instruct

  vector_store:
    provider: chromadb
    config:
      persist_directory: .chroma

generation:
  temperature: 0.0
  max_tokens: 384
  top_k: 1

retrieval:
  top_k: 4
  similarity_threshold: 0.75

security:
  require_auth: false
  enable_cors: true
  cors_origins:
    - http://localhost:3000
```

**Steps:**
1. Install PyYAML
2. Create config loader
3. Add environment variable interpolation
4. Create example YAML configs
5. Test config loading
6. Document config format

---

### 2.5: Gradual Migration to Abstractions

**Strategy:** Make new code paths coexist with old ones

**Update:** `app/main.py`

```python
# Add new imports
from app.protocols import LLMProvider
from app.registry import create_llm
from app.config_loader import load_yaml_config

# Feature flag for new architecture
USE_NEW_ARCHITECTURE = os.getenv("USE_NEW_ARCHITECTURE", "false").lower() == "true"

# Optionally load from YAML
if USE_NEW_ARCHITECTURE:
    CONFIG_FILE = os.getenv("CONFIG_FILE", "config/local.yaml")
    if Path(CONFIG_FILE).exists():
        yaml_config = load_yaml_config(CONFIG_FILE)
        # Create providers from config
        llm_provider = create_llm(
            yaml_config["providers"]["llm"]["provider"],
            yaml_config["providers"]["llm"]["config"]
        )
    else:
        # Fallback to env vars
        pass

# Rest of code unchanged...
```

**Key Point:** Old code still works. New path is opt-in via environment variable.

---

### Stage 2 Validation

**Definition of Done:**
- [ ] Protocols defined and documented
- [ ] Ollama adapter satisfies LLMProvider protocol
- [ ] Registry can discover and create providers
- [ ] YAML configuration works
- [ ] Old code path still works
- [ ] New code path works when enabled
- [ ] Tests pass for both paths

**Deliverables:**
- ✅ Protocol definitions (`protocols.py`)
- ✅ Ollama adapter
- ✅ Plugin registry system
- ✅ YAML configuration support
- ✅ Backward compatibility maintained

---

## 📈 STAGE 3: RAG Quality Improvements
**Goal:** Dramatically improve answer quality
**Prerequisites:** Stage 0, 1 complete (Stage 2 optional)

### 3.1: Semantic Chunking

**Install:**
```txt
# Add to requirements.txt
langchain==0.1.0
langchain-text-splitters==0.0.1
```

**Update:** `scripts/seed_corpus.py`

```python
from langchain.text_splitters import RecursiveCharacterTextSplitter

# Old chunking (naive H2 split)
# sections = re.split(r'\n##\s+', content)

# New chunking (semantic with overlap)
splitter = RecursiveCharacterTextSplitter(
    chunk_size=500,        # ~500 characters per chunk
    chunk_overlap=100,     # 20% overlap between chunks
    separators=["\n##", "\n\n", "\n", " ", ""],  # Try H2, then paragraphs, then sentences
    length_function=len,
)

chunks = splitter.split_text(content)
```

**Steps:**
1. Install langchain
2. Update seed script
3. Re-seed corpus
4. Compare chunk quality
5. Tune chunk_size and overlap
6. Document chunking strategy

---

### 3.2: Cross-Encoder Reranking

**Install:**
```txt
# Add to requirements.txt
# (sentence-transformers already installed, includes cross-encoders)
```

**Create:** `app/reranking.py`

```python
"""
Reranking retrieved documents with cross-encoder.
"""

from sentence_transformers import CrossEncoder
from typing import List, Tuple

class Reranker:
    """Cross-encoder reranker for improving retrieval quality."""

    def __init__(self, model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"):
        self.model = CrossEncoder(model_name)

    def rerank(
        self,
        query: str,
        documents: List[str],
        metadatas: List[dict],
        top_k: int = 5
    ) -> Tuple[List[str], List[dict], List[float]]:
        """
        Rerank documents using cross-encoder.

        Args:
            query: User's question
            documents: Retrieved documents
            metadatas: Document metadatas
            top_k: Number of documents to return

        Returns:
            Reranked (documents, metadatas, scores)
        """
        if not documents:
            return [], [], []

        # Score each document
        pairs = [(query, doc) for doc in documents]
        scores = self.model.predict(pairs)

        # Sort by score (descending)
        ranked = sorted(
            zip(documents, metadatas, scores),
            key=lambda x: x[2],
            reverse=True
        )

        # Take top_k
        ranked = ranked[:top_k]

        # Unzip
        docs, metas, scores = zip(*ranked) if ranked else ([], [], [])

        return list(docs), list(metas), list(scores)

# Singleton
_reranker: Reranker | None = None

def get_reranker() -> Reranker:
    """Get or create reranker instance."""
    global _reranker
    if _reranker is None:
        _reranker = Reranker()
    return _reranker
```

**Update:** `app/main.py`

```python
from app.config import ENABLE_RERANKING  # Add to config.py
from app.reranking import get_reranker

@app.post("/ask", response_model=Answer)
async def ask_question(q: AskQuestion):
    # ... existing retrieval code ...
    documents, metadatas, distances = store.query(q.question, n_results=20)  # Get more candidates

    # Rerank if enabled
    if ENABLE_RERANKING:
        reranker = get_reranker()
        documents, metadatas, scores = reranker.rerank(
            query=q.question,
            documents=documents,
            metadatas=metadatas,
            top_k=TOP_K
        )
        # Use reranked scores instead of distances
        distances = [1.0 - score for score in scores]  # Convert to distances

    # Rest of code unchanged...
```

**Steps:**
1. Create reranking module
2. Implement cross-encoder reranking
3. Add config flag (ENABLE_RERANKING)
4. Integrate into retrieval pipeline
5. Benchmark quality improvement
6. Document reranking

---

### 3.3: Hybrid Search (Vector + BM25)

**Install:**
```txt
# Add to requirements.txt
rank-bm25==0.2.2
```

**Create:** `app/hybrid_search.py`

```python
"""
Hybrid search combining vector and BM25 keyword search.
"""

from rank_bm25 import BM25Okapi
from typing import List, Tuple, Dict, Any
from collections import defaultdict

def reciprocal_rank_fusion(
    results_lists: List[List[Tuple[str, Any, float]]],
    k: int = 60
) -> List[Tuple[str, Any, float]]:
    """
    Combine multiple result lists using Reciprocal Rank Fusion.

    Args:
        results_lists: List of [(doc, metadata, score), ...]
        k: Fusion parameter (default: 60)

    Returns:
        Fused results sorted by score
    """
    scores = defaultdict(float)
    doc_map = {}
    meta_map = {}

    for results in results_lists:
        for rank, (doc, meta, _) in enumerate(results, 1):
            doc_id = meta.get("id", doc[:50])  # Use ID or first 50 chars as key
            scores[doc_id] += 1.0 / (k + rank)
            doc_map[doc_id] = doc
            meta_map[doc_id] = meta

    # Sort by fused score
    fused = [
        (doc_map[doc_id], meta_map[doc_id], score)
        for doc_id, score in sorted(scores.items(), key=lambda x: x[1], reverse=True)
    ]

    return fused

class HybridSearcher:
    """Combines vector and keyword search."""

    def __init__(self, vector_store):
        self.vector_store = vector_store
        self.bm25 = None
        self.documents = []
        self.metadatas = []
        self._build_bm25_index()

    def _build_bm25_index(self):
        """Build BM25 index from vector store."""
        # Get all documents
        all_docs = self.vector_store.collection.get()
        if not all_docs or not all_docs.get("documents"):
            return

        self.documents = all_docs["documents"]
        self.metadatas = all_docs["metadatas"]

        # Tokenize for BM25
        tokenized_docs = [doc.lower().split() for doc in self.documents]
        self.bm25 = BM25Okapi(tokenized_docs)

    def search(self, query: str, k: int = 10) -> Tuple[List[str], List[Dict], List[float]]:
        """
        Hybrid search combining vector and BM25.

        Args:
            query: Search query
            k: Number of results

        Returns:
            (documents, metadatas, scores)
        """
        # Vector search
        vector_docs, vector_metas, vector_dists = self.vector_store.query(query, n_results=k*2)
        vector_results = list(zip(vector_docs, vector_metas, vector_dists))

        # BM25 search
        if self.bm25:
            tokenized_query = query.lower().split()
            bm25_scores = self.bm25.get_scores(tokenized_query)
            bm25_results = [
                (doc, meta, score)
                for doc, meta, score in zip(self.documents, self.metadatas, bm25_scores)
            ]
            bm25_results = sorted(bm25_results, key=lambda x: x[2], reverse=True)[:k*2]
        else:
            bm25_results = []

        # Fuse results
        fused = reciprocal_rank_fusion([vector_results, bm25_results])

        # Take top k
        fused = fused[:k]

        # Unzip
        if fused:
            docs, metas, scores = zip(*fused)
            return list(docs), list(metas), list(scores)
        else:
            return [], [], []
```

**Update:** `app/main.py`

```python
from app.hybrid_search import HybridSearcher
from app.config import ENABLE_HYBRID_SEARCH  # Add to config.py

# Initialize hybrid searcher (optional)
hybrid_searcher = None
if ENABLE_HYBRID_SEARCH:
    hybrid_searcher = HybridSearcher(get_vector_store())

@app.post("/ask", response_model=Answer)
async def ask_question(q: AskQuestion):
    # Use hybrid search if enabled
    if ENABLE_HYBRID_SEARCH and hybrid_searcher:
        documents, metadatas, scores = hybrid_searcher.search(q.question, k=20)
        # Convert scores to distances for compatibility
        distances = [1.0 - score for score in scores]
    else:
        documents, metadatas, distances = store.query(q.question)

    # Rest of code unchanged...
```

**Steps:**
1. Install rank-bm25
2. Create hybrid search module
3. Implement RRF algorithm
4. Add config flag
5. Benchmark hybrid vs vector-only
6. Document hybrid search

---

### Stage 3 Validation

**Definition of Done:**
- [ ] Semantic chunking produces better chunks
- [ ] Reranking improves top-k results
- [ ] Hybrid search works
- [ ] Quality metrics improved
- [ ] Config flags work
- [ ] Performance acceptable
- [ ] Documentation updated

**Deliverables:**
- ✅ Semantic chunking system
- ✅ Cross-encoder reranking
- ✅ Hybrid search implementation
- ✅ Quality benchmarks showing improvement
- ✅ Configuration options

---

## 🔌 STAGE 4: Multi-Provider Support
**Goal:** Support multiple LLM and vector store providers
**Prerequisites:** Stage 2 complete

### 4.1: OpenAI LLM Adapter

**Install:**
```txt
# Add to requirements.txt
openai==1.6.1
```

**Create:** `app/adapters/llm/openai_adapter.py`

```python
"""OpenAI LLM adapter."""

from openai import AsyncOpenAI
from app.protocols import LLMProvider, GenerationConfig
from app.registry import llm_provider

@llm_provider("openai")
class OpenAILLM:
    """OpenAI implementation of LLMProvider."""

    def __init__(self, api_key: str, model: str = "gpt-4o-mini"):
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model

    @property
    def model_name(self) -> str:
        return self.model

    async def generate(self, prompt: str, config: GenerationConfig) -> str:
        """Generate using OpenAI."""
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": prompt}],
            temperature=config.temperature,
            max_tokens=config.max_tokens,
            top_p=config.top_p
        )

        return response.choices[0].message.content.strip()
```

**Config:** `config/openai.yaml`

```yaml
providers:
  llm:
    provider: openai
    config:
      api_key: ${OPENAI_API_KEY}
      model: gpt-4o-mini
```

**Steps:**
1. Install OpenAI SDK
2. Create adapter
3. Register with decorator
4. Test with real API key
5. Document usage

---

### 4.2: Qdrant Vector Store Adapter

**Install:**
```txt
# Add to requirements.txt
qdrant-client==1.7.0
```

**Create:** `app/adapters/vector_stores/qdrant_adapter.py`

```python
"""Qdrant vector store adapter."""

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
from typing import List, Dict, Any, Tuple
from app.registry import vector_store_provider

@vector_store_provider("qdrant")
class QdrantVectorStore:
    """Qdrant implementation of VectorStore protocol."""

    def __init__(
        self,
        url: str = "http://localhost:6333",
        collection_name: str = "faq",
        vector_size: int = 384
    ):
        self.client = QdrantClient(url=url)
        self.collection_name = collection_name

        # Create collection if not exists
        try:
            self.client.get_collection(collection_name)
        except Exception:
            self.client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(
                    size=vector_size,
                    distance=Distance.COSINE
                )
            )

    def upsert(
        self,
        doc_id: str,
        text: str,
        tags: List[str],
        metadata: Dict[str, Any] | None = None
    ) -> None:
        """Upsert document to Qdrant."""
        # Need to generate embedding first
        # TODO: Integrate with embedding provider
        pass

    def query(
        self,
        query_text: str,
        n_results: int = 4
    ) -> Tuple[List[str], List[Dict[str, Any]], List[float]]:
        """Query Qdrant."""
        # Need to generate query embedding first
        # TODO: Integrate with embedding provider
        pass

    # ... implement other methods ...
```

**Steps:**
1. Install Qdrant client
2. Create adapter
3. Implement vector store protocol
4. Add embedding integration
5. Test with local Qdrant
6. Document usage

---

### Stage 4 Validation

**Definition of Done:**
- [ ] OpenAI adapter works
- [ ] Qdrant adapter works
- [ ] Provider swapping works via config
- [ ] All adapters satisfy protocols
- [ ] Tests pass
- [ ] Documentation complete

**Deliverables:**
- ✅ OpenAI LLM adapter
- ✅ Qdrant vector store adapter
- ✅ Provider comparison guide
- ✅ Configuration examples

---

## 🧪 STAGE 5: Testing & Production Readiness
**Goal:** Comprehensive testing and deployment preparation
**Prerequisites:** All previous stages complete

### 5.1: Comprehensive Test Suite

**Create:** `tests/` directory structure

```
tests/
├── unit/
│   ├── test_config.py
│   ├── test_security.py
│   ├── test_retrieval.py
│   └── test_generation.py
├── integration/
│   ├── test_rag_pipeline.py
│   └── test_api_endpoints.py
├── e2e/
│   └── test_ask_flow.py
└── fixtures/
    └── test_corpus.md
```

**Example:** `tests/unit/test_config.py`

```python
"""Test configuration system."""

import pytest
from app.config import SIMILARITY_THRESHOLD, validate_config

def test_similarity_threshold_from_env(monkeypatch):
    """Test that similarity threshold respects environment variable."""
    monkeypatch.setenv("SIMILARITY_THRESHOLD", "0.85")
    # Reload config
    import importlib
    import app.config
    importlib.reload(app.config)

    assert app.config.SIMILARITY_THRESHOLD == 0.85

def test_config_validation_passes():
    """Test that config validation passes with valid config."""
    validate_config()  # Should not raise

# More tests...
```

**Steps:**
1. Create test directory structure
2. Write unit tests for all modules
3. Write integration tests
4. Write end-to-end tests
5. Set up CI/CD (GitHub Actions)
6. Aim for >80% coverage

---

### 5.2: Performance Benchmarking

**Create:** `tests/performance/benchmark.py`

```python
"""Performance benchmarks."""

import time
import asyncio
from app.main import ask_question
from app.models import AskQuestion

async def benchmark_ask_latency(n=100):
    """Benchmark ask endpoint latency."""
    question = AskQuestion(question="What are your hours?", scope="public")

    latencies = []
    for _ in range(n):
        start = time.time()
        await ask_question(question)
        latency = (time.time() - start) * 1000  # ms
        latencies.append(latency)

    print(f"P50: {sorted(latencies)[len(latencies)//2]:.2f}ms")
    print(f"P95: {sorted(latencies)[int(len(latencies)*0.95)]:.2f}ms")
    print(f"P99: {sorted(latencies)[int(len(latencies)*0.99)]:.2f}ms")

if __name__ == "__main__":
    asyncio.run(benchmark_ask_latency())
```

**Steps:**
1. Create benchmark suite
2. Benchmark key operations
3. Identify bottlenecks
4. Optimize hot paths
5. Document performance targets

---

### 5.3: Production Deployment

**Create:** `docker-compose.prod.yml`

```yaml
version: '3.8'

services:
  ollama:
    image: ollama/ollama
    volumes:
      - ollama-data:/root/.ollama
    ports:
      - "11434:11434"

  qdrant:
    image: qdrant/qdrant
    volumes:
      - qdrant-data:/qdrant/storage
    ports:
      - "6333:6333"

  faq-bot:
    build: .
    depends_on:
      - ollama
      - qdrant
    environment:
      - OLLAMA_ENDPOINT=http://ollama:11434
      - VECTOR_STORE_TYPE=qdrant
      - QDRANT_URL=http://qdrant:6333
      - REQUIRE_AUTH=true
      - ENABLE_CORS=true
      - CORS_ORIGINS=https://yourdomain.com
    ports:
      - "8000:8000"
    volumes:
      - ./corpus:/app/corpus:ro  # Read-only
      - ./logs:/app/logs
    restart: unless-stopped

volumes:
  ollama-data:
  qdrant-data:
```

**Steps:**
1. Create production Docker Compose
2. Configure secrets management
3. Set up reverse proxy (nginx)
4. Configure SSL/TLS
5. Set up monitoring
6. Document deployment

---

### Stage 5 Validation

**Definition of Done:**
- [ ] Test coverage >80%
- [ ] All tests pass
- [ ] Performance benchmarks meet targets
- [ ] Production deployment works
- [ ] Monitoring operational
- [ ] Documentation complete

**Deliverables:**
- ✅ Comprehensive test suite
- ✅ Performance benchmarks
- ✅ Production deployment config
- ✅ Operations runbook

---

## 📈 Success Metrics

### Technical Metrics

| Metric | Baseline | Target | Current |
|--------|----------|--------|---------|
| Bugs | 4 critical | 0 | ? |
| Test Coverage | ~30% | >80% | ? |
| P95 Latency | Unknown | <500ms | ? |
| Similarity Accuracy | Broken | Correct | ? |
| Provider Swap Time | N/A | <5 min | ? |

### Quality Metrics

| Metric | Measurement Method |
|--------|-------------------|
| Answer Quality | Human evaluation on test set |
| Refusal Rate | % of questions refused |
| RBAC Effectiveness | Zero unauthorized access |
| Cache Hit Rate | >60% for common questions |

---

## 🔄 Implementation Sequence

### Recommended Order

**Must Do (In Order):**
1. Stage 0 (Bug fixes) → CRITICAL
2. Stage 1 (Security) → HIGH PRIORITY
3. Stage 5.1 (Testing) → Validate fixes work

**Should Do (Flexible Order):**
4. Stage 3 (RAG improvements) → Quality improvements
5. Stage 2 (Abstractions) → Architecture foundation
6. Stage 4 (Multi-provider) → Flexibility

**Nice to Have:**
7. Stage 5.2-5.3 (Production) → When ready to deploy

### Parallel Work Possible

- Stage 0 + Stage 1.5 (CORS fix)
- Stage 2 + Stage 3 (can be done in parallel)
- Stage 1.4 (Logging) + Stage 5.1 (Testing)

---

## 📚 Documentation Requirements

### Per Stage Documentation

Each stage must deliver:
- [ ] Code documentation (docstrings)
- [ ] API documentation (if endpoints changed)
- [ ] Configuration documentation
- [ ] Migration guide (if breaking changes)
- [ ] Testing documentation
- [ ] Examples

---

## ✅ Stage Completion Checklist

### Template for Each Stage

**Stage X Complete When:**
- [ ] All code written and reviewed
- [ ] All tests passing
- [ ] Documentation updated
- [ ] Changelog updated
- [ ] Performance validated
- [ ] Security reviewed (if applicable)
- [ ] Deployed to staging
- [ ] Stakeholder approval

---

## 🎯 Next Steps

### Immediate Actions

1. **Review this plan** with team
2. **Start Stage 0** immediately (bug fixes)
3. **Set up project tracking** (GitHub Projects, Jira)
4. **Create feature branches** for each stage
5. **Establish CI/CD pipeline**

### First Sprint Goals

**Stage 0 Focus:**
- Fix hardcoded threshold
- Fix distance metric
- Enable cached query
- Add input validation
- All bugs resolved

**Success Criteria:**
- Configuration system works
- Similarity scores are correct
- Tests pass
- System functions correctly

---

**Document Version:** 1.0
**Last Updated:** 2025-10-08
**Next Review:** After Stage 0 completion

---

*This is a living document. Update as implementation progresses and new information emerges.*
