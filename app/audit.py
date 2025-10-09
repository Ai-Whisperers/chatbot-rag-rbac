"""
Comprehensive audit logging for security and compliance.

Logs all security-relevant events to structured JSON logs.
"""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any
from functools import wraps

from app.config import PROJECT_ROOT

# ==================== CONFIGURATION ====================
AUDIT_LOG_DIR = PROJECT_ROOT / "logs"
AUDIT_LOG_FILE = AUDIT_LOG_DIR / "audit.log"

# Ensure log directory exists
AUDIT_LOG_DIR.mkdir(exist_ok=True)

# ==================== LOGGER SETUP ====================
audit_logger = logging.getLogger("audit")
audit_logger.setLevel(logging.INFO)
audit_logger.propagate = False  # Don't propagate to root logger

# File handler with JSON formatting
file_handler = logging.FileHandler(AUDIT_LOG_FILE, encoding="utf-8")
file_handler.setLevel(logging.INFO)

# Custom formatter for structured logs
class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "event_type": getattr(record, "event_type", "unknown"),
            "message": record.getMessage(),
        }

        # Add extra fields if present
        if hasattr(record, "extra_data"):
            log_data.update(record.extra_data)

        return json.dumps(log_data)

file_handler.setFormatter(JSONFormatter())
audit_logger.addHandler(file_handler)


# ==================== AUDIT FUNCTIONS ====================

def log_event(
    event_type: str,
    message: str,
    user_id: Optional[str] = None,
    scope: Optional[str] = None,
    **extra_data
):
    """
    Log a security audit event.

    Args:
        event_type: Type of event (question_asked, document_upserted, etc.)
        message: Human-readable message
        user_id: Optional user identifier
        scope: Optional RBAC scope
        **extra_data: Additional structured data to log
    """
    extra = {
        "user_id": user_id,
        "scope": scope,
        **extra_data
    }

    # Remove None values
    extra = {k: v for k, v in extra.items() if v is not None}

    audit_logger.info(
        message,
        extra={"event_type": event_type, "extra_data": extra}
    )


def log_question_asked(
    question: str,
    scope: str,
    user_id: Optional[str] = None,
    retrieved_count: int = 0,
    filtered_count: int = 0,
    is_refusal: bool = False,
    ip_address: Optional[str] = None
):
    """Log when a question is asked."""
    log_event(
        event_type="question_asked",
        message=f"Question asked in scope '{scope}'",
        user_id=user_id,
        scope=scope,
        question=question[:200],  # Truncate for log size
        retrieved_count=retrieved_count,
        filtered_count=filtered_count,
        is_refusal=is_refusal,
        ip_address=ip_address
    )


def log_document_upserted(
    doc_id: str,
    tags: list,
    user_id: Optional[str] = None,
    is_batch: bool = False
):
    """Log when a document is upserted."""
    log_event(
        event_type="document_upserted",
        message=f"Document '{doc_id}' upserted",
        user_id=user_id,
        doc_id=doc_id,
        tags=tags,
        is_batch=is_batch
    )


def log_document_deleted(doc_id: str, user_id: Optional[str] = None):
    """Log when a document is deleted."""
    log_event(
        event_type="document_deleted",
        message=f"Document '{doc_id}' deleted",
        user_id=user_id,
        doc_id=doc_id
    )


def log_auth_attempt(
    success: bool,
    user_id: Optional[str] = None,
    ip_address: Optional[str] = None,
    reason: Optional[str] = None
):
    """Log authentication attempts."""
    log_event(
        event_type="auth_attempt",
        message=f"Authentication {'successful' if success else 'failed'}",
        user_id=user_id,
        success=success,
        ip_address=ip_address,
        reason=reason
    )


def log_rate_limit_exceeded(
    ip_address: Optional[str] = None,
    endpoint: Optional[str] = None
):
    """Log rate limit violations."""
    log_event(
        event_type="rate_limit_exceeded",
        message="Rate limit exceeded",
        ip_address=ip_address,
        endpoint=endpoint
    )


def log_injection_attempt(
    question: str,
    reason: str,
    ip_address: Optional[str] = None,
    user_id: Optional[str] = None
):
    """Log detected injection attempts."""
    log_event(
        event_type="injection_attempt",
        message="Prompt injection attempt detected",
        user_id=user_id,
        question=question[:200],
        reason=reason,
        ip_address=ip_address
    )


def log_scope_violation(
    user_id: str,
    requested_scope: str,
    user_scopes: list,
    ip_address: Optional[str] = None
):
    """Log when a user tries to access a scope they don't have."""
    log_event(
        event_type="scope_violation",
        message=f"User attempted to access scope '{requested_scope}' without permission",
        user_id=user_id,
        requested_scope=requested_scope,
        user_scopes=user_scopes,
        ip_address=ip_address
    )


def log_user_created(admin_id: str, new_user_id: str, scopes: list):
    """Log when a new user is created."""
    log_event(
        event_type="user_created",
        message=f"User '{new_user_id}' created by admin '{admin_id}'",
        user_id=admin_id,
        new_user_id=new_user_id,
        scopes=scopes
    )


def log_user_revoked(admin_id: str, revoked_user_id: str):
    """Log when a user is revoked."""
    log_event(
        event_type="user_revoked",
        message=f"User '{revoked_user_id}' revoked by admin '{admin_id}'",
        user_id=admin_id,
        revoked_user_id=revoked_user_id
    )


def log_policy_reload(user_id: Optional[str] = None):
    """Log when security policies are reloaded."""
    log_event(
        event_type="policy_reload",
        message="Security policies reloaded",
        user_id=user_id
    )


# ==================== AUDIT DECORATOR ====================

def audit_endpoint(event_type: str):
    """
    Decorator to automatically audit endpoint calls.

    Usage:
        @audit_endpoint("question_asked")
        async def ask_question(...):
            ...
    """
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                result = await func(*args, **kwargs)
                log_event(
                    event_type=event_type,
                    message=f"Endpoint {func.__name__} called successfully"
                )
                return result
            except Exception as e:
                log_event(
                    event_type=f"{event_type}_error",
                    message=f"Endpoint {func.__name__} failed: {str(e)}"
                )
                raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                result = func(*args, **kwargs)
                log_event(
                    event_type=event_type,
                    message=f"Endpoint {func.__name__} called successfully"
                )
                return result
            except Exception as e:
                log_event(
                    event_type=f"{event_type}_error",
                    message=f"Endpoint {func.__name__} failed: {str(e)}"
                )
                raise

        # Return appropriate wrapper based on function type
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator
