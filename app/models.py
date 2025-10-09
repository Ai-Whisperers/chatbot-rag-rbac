"""
Pydantic models for API contracts.
Clean, validated data structures for requests and responses.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator
from app.config import MAX_QUESTION_LENGTH, MAX_DOCUMENT_LENGTH


class UpsertDocument(BaseModel):
    """Request model for upserting a document into the corpus."""

    id: str = Field(..., description="Unique document identifier")
    text: str = Field(
        ...,
        min_length=1,
        max_length=MAX_DOCUMENT_LENGTH,
        description=f"Document content (max {MAX_DOCUMENT_LENGTH} characters)"
    )
    tags: List[str] = Field(default=["faq"], description="Access control tags")
    metadata: Optional[Dict[str, Any]] = Field(default=None, description="Additional metadata")

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, v: List[str]) -> List[str]:
        """Ensure tags are non-empty and lowercase."""
        if not v:
            raise ValueError("At least one tag is required")
        return [tag.lower().strip() for tag in v]


class AskQuestion(BaseModel):
    """Request model for asking a question."""

    question: str = Field(
        ...,
        min_length=1,
        max_length=MAX_QUESTION_LENGTH,
        description=f"User's question (max {MAX_QUESTION_LENGTH} characters)"
    )
    scope: str = Field(default="public", description="RBAC scope (public, support, admin)")
    user_id: Optional[str] = Field(default="anonymous", description="User identifier for logging")

    @field_validator("scope")
    @classmethod
    def validate_scope(cls, v: str) -> str:
        """Normalize scope to lowercase."""
        return v.lower().strip()

    @field_validator("question")
    @classmethod
    def validate_question(cls, v: str) -> str:
        """Trim whitespace from question."""
        return v.strip()


class Answer(BaseModel):
    """Response model for answered questions."""

    answer: str = Field(..., description="Generated answer or refusal message")
    grounding: List[str] = Field(default=[], description="Source references")
    policy: str = Field(..., description="RBAC scope applied")
    retrieved_count: int = Field(default=0, description="Number of documents retrieved")
    filtered_count: int = Field(default=0, description="Number of documents after filtering")
    model_used: Optional[str] = Field(default=None, description="LLM model name")


class HealthCheck(BaseModel):
    """Health check response."""

    status: str = Field(..., description="Service status")
    version: str = Field(..., description="API version")
    corpus_loaded: bool = Field(..., description="Whether corpus is loaded")
    model_available: bool = Field(..., description="Whether LLM is available")
    collection_count: int = Field(default=0, description="Number of documents in vector store")


class CorpusMetadata(BaseModel):
    """Corpus metadata structure."""

    version: str = Field(..., description="Corpus version")
    last_updated: str = Field(..., description="ISO timestamp of last update")
    document_count: int = Field(..., description="Total documents in corpus")
    content_hash: str = Field(..., description="SHA256 hash of corpus content")
    tags: List[str] = Field(default=[], description="All available tags")


class BatchUpsert(BaseModel):
    """Batch upsert multiple documents."""

    documents: List[UpsertDocument] = Field(..., min_length=1, description="Documents to upsert")
