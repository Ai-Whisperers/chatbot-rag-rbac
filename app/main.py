"""
FastAPI application entry point.
Exposes endpoints for document management and question answering.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import httpx
from typing import List

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
    REFUSAL_MESSAGE
)
from app.security import get_security_policy
from app.retrieval import get_vector_store, VectorStore
from app.generation import answer_question
from app import __version__


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

# CORS middleware
if ENABLE_CORS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
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
    store = get_vector_store()
    store.upsert(
        doc_id=doc.id,
        text=doc.text,
        tags=doc.tags,
        metadata=doc.metadata
    )

    return {"status": "ok", "id": doc.id}


@app.post("/batch_upsert")
def batch_upsert_documents(batch: BatchUpsert):
    """
    Batch upsert multiple documents.

    More efficient than individual upserts for bulk operations.
    """
    store = get_vector_store()

    documents = [
        (doc.id, doc.text, doc.tags, doc.metadata)
        for doc in batch.documents
    ]

    store.batch_upsert(documents)

    return {
        "status": "ok",
        "count": len(batch.documents)
    }


@app.post("/ask", response_model=Answer)
async def ask_question(q: AskQuestion):
    """
    Ask a question and get an answer grounded in the corpus.

    - **question**: The user's question
    - **scope**: RBAC scope (public, support, admin)
    - **user_id**: Optional user identifier for logging

    Returns answer with grounding information and policy metadata.
    """
    security = get_security_policy()
    store = get_vector_store()

    # Validate scope
    if not security.validate_scope(q.scope):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid scope '{q.scope}'. Available: {security.get_available_scopes()}"
        )

    # Retrieve candidate documents
    documents, metadatas, distances = store.query(q.question)

    # Filter by RBAC and similarity threshold
    context_chunks: List[str] = []
    for doc, meta, dist in zip(documents, metadatas, distances):
        similarity = VectorStore.distance_to_similarity(dist)
        doc_tags = meta.get("tags", [])

        if similarity >= 0.75 and security.scope_allowed(q.scope, doc_tags):
            context_chunks.append(doc)

    # Get policy hash for audit trail
    policy_hash = security.get_policy_hash(q.scope)

    # Generate answer
    answer_text, is_refusal = await answer_question(
        question=q.question,
        context_chunks=context_chunks,
        scope=q.scope,
        policy_hash=policy_hash
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

    return {
        "status": "reloaded",
        "scopes": security.get_available_scopes()
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
