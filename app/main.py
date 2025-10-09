"""
FastAPI application entry point.
Exposes endpoints for document management and question answering.
"""

from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from contextlib import asynccontextmanager
import httpx
import json
from typing import List, Optional
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.models import (
    UpsertDocument,
    AskQuestion,
    Answer,
    HealthCheck,
    BatchUpsert
)
from app.config import (
    validate_config,
    ENABLE_CORS,
    CORS_ORIGINS,
    MODEL_ENDPOINT,
    MODEL_NAME,
    REFUSAL_MESSAGE,
    SIMILARITY_THRESHOLD,
    REQUIRE_AUTH,
    ENABLE_RATE_LIMIT,
    RATE_LIMIT_PER_MINUTE
)
from app.security import get_security_policy
from app.security.input_validation import validate_question, validate_document_text
from app.retrieval import get_vector_store, VectorStore, cached_query
from app.generation import answer_question
from app.auth import get_current_user, require_auth, User, get_api_key_manager
from app.audit import (
    log_question_asked,
    log_document_upserted,
    log_document_deleted,
    log_rate_limit_exceeded,
    log_injection_attempt,
    log_scope_violation,
    log_user_created,
    log_user_revoked,
    log_policy_reload
)
from app import __version__


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware to add security headers to all responses."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

        return response


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for startup and shutdown."""
    # Startup
    print("🚀 Starting FAQ Bot...")
    validate_config()

    # Initialize singletons
    _ = get_security_policy()
    _ = get_vector_store()

    print("✓ FAQ Bot ready")

    yield

    # Shutdown
    print("👋 Shutting down FAQ Bot...")


# Create FastAPI app
app = FastAPI(
    title="Deterministic FAQ Bot",
    description="Policy-aware FAQ chatbot with RAG and RBAC",
    version=__version__,
    lifespan=lifespan
)

# Rate limiting
if ENABLE_RATE_LIMIT:
    limiter = Limiter(
        key_func=get_remote_address,
        default_limits=[f"{RATE_LIMIT_PER_MINUTE}/minute"]
    )
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
else:
    # No-op limiter if disabled
    limiter = None

# Security headers middleware (applied to all responses)
app.add_middleware(SecurityHeadersMiddleware)

# CORS middleware
if ENABLE_CORS:
    # Only allow wildcard if explicitly set to "*"
    allow_credentials = "*" not in CORS_ORIGINS

    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_credentials=allow_credentials,  # Must be False if origins includes "*"
        allow_methods=["GET", "POST", "DELETE"],  # Explicit methods only
        allow_headers=["Authorization", "Content-Type"],  # Explicit headers only
        max_age=600,  # Cache preflight for 10 minutes
    )


@app.get("/health", response_model=HealthCheck)
async def health_check():
    """Health check endpoint."""
    store = get_vector_store()

    # Check if model is available
    model_available = False
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{MODEL_ENDPOINT}/api/tags")
            model_available = response.status_code == 200
    except Exception:
        model_available = False

    return HealthCheck(
        status="healthy",
        version=__version__,
        corpus_loaded=store.count() > 0,
        model_available=model_available,
        collection_count=store.count()
    )


@app.post("/upsert")
def upsert_document(doc: UpsertDocument):
    """
    Upsert a single document into the corpus.

    - **id**: Unique document identifier
    - **text**: Document content
    - **tags**: Access control tags (e.g., ["faq", "pricing"])
    - **metadata**: Optional additional metadata
    """
    # Validate and sanitize document text
    try:
        clean_text = validate_document_text(doc.text)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    store = get_vector_store()
    store.upsert(
        doc_id=doc.id,
        text=clean_text,
        tags=doc.tags,
        metadata=doc.metadata
    )

    # Audit log
    log_document_upserted(doc_id=doc.id, tags=doc.tags, is_batch=False)

    return {"status": "ok", "id": doc.id}


@app.post("/batch_upsert")
def batch_upsert_documents(batch: BatchUpsert):
    """
    Batch upsert multiple documents.

    More efficient than individual upserts for bulk operations.
    """
    # Validate and sanitize all documents
    validated_documents = []
    for doc in batch.documents:
        try:
            clean_text = validate_document_text(doc.text)
            validated_documents.append((doc.id, clean_text, doc.tags, doc.metadata))
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail=f"Document '{doc.id}' failed validation: {str(e)}"
            )

    store = get_vector_store()
    store.batch_upsert(validated_documents)

    # Audit log each document
    for doc in batch.documents:
        log_document_upserted(doc_id=doc.id, tags=doc.tags, is_batch=True)

    return {
        "status": "ok",
        "count": len(batch.documents)
    }


@app.post("/ask", response_model=Answer)
async def ask_question(
    request: Request,
    q: AskQuestion,
    user: Optional[User] = Depends(get_current_user)
):
    """
    Ask a question and get an answer grounded in the corpus.

    - **question**: The user's question
    - **scope**: RBAC scope (public, support, admin)
    - **user_id**: Optional user identifier for logging

    Authentication: Optional (configurable via REQUIRE_AUTH)
    - If REQUIRE_AUTH=true, API key required in Authorization header
    - User must have access to requested scope

    Rate Limiting: Configured via RATE_LIMIT_PER_MINUTE (default: 10/minute)

    Returns answer with grounding information and policy metadata.
    """
    # Get client IP for audit logging
    client_ip = get_remote_address(request)

    # Apply rate limit manually if enabled
    if ENABLE_RATE_LIMIT and limiter:
        try:
            await limiter.check_request_limits(request)
        except RateLimitExceeded:
            log_rate_limit_exceeded(ip_address=client_ip, endpoint="/ask")
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded. Please try again later."
            )

    # Validate and sanitize question
    try:
        clean_question = validate_question(q.question)
    except ValueError as e:
        log_injection_attempt(
            question=q.question,
            reason=str(e),
            ip_address=client_ip,
            user_id=user.user_id if user else None
        )
        raise HTTPException(status_code=400, detail=str(e))

    security = get_security_policy()
    store = get_vector_store()

    # Validate scope
    if not security.validate_scope(q.scope):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid scope '{q.scope}'. Available: {security.get_available_scopes()}"
        )

    # If authentication is required, verify user has access to scope
    if REQUIRE_AUTH:
        if user is None:
            raise HTTPException(
                status_code=401,
                detail="Authentication required. Provide API key in Authorization header."
            )
        if not user.has_scope(q.scope):
            log_scope_violation(
                user_id=user.user_id,
                requested_scope=q.scope,
                user_scopes=user.scopes,
                ip_address=client_ip
            )
            raise HTTPException(
                status_code=403,
                detail=f"Access denied. User does not have '{q.scope}' scope."
            )

    # Retrieve candidate documents (with caching for performance)
    result_json = cached_query(clean_question)
    result = json.loads(result_json)
    documents = result["documents"]
    metadatas = result["metadatas"]
    distances = result["distances"]

    # Filter by RBAC and similarity threshold
    context_chunks: List[str] = []
    for doc, meta, dist in zip(documents, metadatas, distances):
        similarity = VectorStore.distance_to_similarity(dist)
        doc_tags = meta.get("tags", [])

        if similarity >= SIMILARITY_THRESHOLD and security.scope_allowed(q.scope, doc_tags):
            context_chunks.append(doc)

    # Get policy hash for audit trail
    policy_hash = security.get_policy_hash(q.scope)

    # Generate answer
    answer_text, is_refusal = await answer_question(
        question=clean_question,
        context_chunks=context_chunks,
        scope=q.scope,
        policy_hash=policy_hash
    )

    # Audit log the question
    log_question_asked(
        question=clean_question,
        scope=q.scope,
        user_id=user.user_id if user else q.user_id,
        retrieved_count=len(documents),
        filtered_count=len(context_chunks),
        is_refusal=is_refusal,
        ip_address=client_ip
    )

    return Answer(
        answer=answer_text,
        grounding=[] if is_refusal else ["internal documentation"],
        policy=q.scope,
        retrieved_count=len(documents),
        filtered_count=len(context_chunks),
        model_used=MODEL_NAME
    )


@app.delete("/document/{doc_id}")
def delete_document(doc_id: str):
    """Delete a document by ID."""
    store = get_vector_store()
    store.delete(doc_id)

    # Audit log
    log_document_deleted(doc_id=doc_id)

    return {"status": "ok", "deleted": doc_id}


@app.get("/corpus/stats")
def corpus_stats():
    """Get corpus statistics."""
    store = get_vector_store()

    return {
        "total_documents": store.count(),
        "available_tags": store.get_all_tags(),
    }


@app.post("/security/reload")
def reload_security_policies():
    """
    Reload security policies from disk.
    Useful for updating RBAC without restart.
    """
    security = get_security_policy()
    security.reload_policies()

    # Audit log
    log_policy_reload()

    return {
        "status": "reloaded",
        "scopes": security.get_available_scopes()
    }


# ==================== Admin Endpoints (API Key Management) ====================

@app.post("/admin/users/create")
def create_user(
    user_id: str,
    scopes: List[str],
    admin: User = Depends(require_auth)
):
    """
    Create a new user with API key.

    Requires authentication.
    Returns API key (only shown once - save it!)

    **Parameters:**
    - user_id: Unique identifier for user
    - scopes: List of allowed scopes (e.g., ["public", "support"])
    """
    manager = get_api_key_manager()

    # Generate API key
    api_key = manager.create_user(user_id=user_id, scopes=scopes)

    # Audit log
    log_user_created(admin_id=admin.user_id, new_user_id=user_id, scopes=scopes)

    return {
        "status": "created",
        "user_id": user_id,
        "scopes": scopes,
        "api_key": api_key,
        "note": "Save this API key - it won't be shown again!"
    }


@app.delete("/admin/users/{user_id}")
def revoke_user(
    user_id: str,
    admin: User = Depends(require_auth)
):
    """
    Revoke user's API key.

    Requires authentication.
    """
    manager = get_api_key_manager()

    revoked = manager.revoke_user(user_id)

    if not revoked:
        raise HTTPException(status_code=404, detail=f"User '{user_id}' not found")

    # Audit log
    log_user_revoked(admin_id=admin.user_id, revoked_user_id=user_id)

    return {
        "status": "revoked",
        "user_id": user_id
    }


@app.get("/admin/users")
def list_users(admin: User = Depends(require_auth)):
    """
    List all users (without API keys).

    Requires authentication.
    """
    manager = get_api_key_manager()
    users = manager.list_users()

    return {
        "users": users,
        "count": len(users)
    }


if __name__ == "__main__":
    import uvicorn
    from app.config import API_HOST, API_PORT

    uvicorn.run(
        "app.main:app",
        host=API_HOST,
        port=API_PORT,
        reload=False
    )
