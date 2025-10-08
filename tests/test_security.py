"""
Tests for RBAC security policy enforcement.
"""

import pytest
from app.security import SecurityPolicy


@pytest.fixture
def security_policy():
    """Create a test security policy."""
    return SecurityPolicy()


def test_scope_allowed_with_matching_tag(security_policy):
    """Test that scope allows access when document has allowed tag."""
    doc_tags = ["faq", "pricing"]
    assert security_policy.scope_allowed("public", doc_tags) is True


def test_scope_denied_with_denied_tag(security_policy):
    """Test that scope denies access when document has denied tag."""
    doc_tags = ["faq", "internal"]  # "internal" is in public's deny list
    assert security_policy.scope_allowed("public", doc_tags) is False


def test_scope_denied_without_allowed_tag(security_policy):
    """Test that scope denies access when document has no allowed tags."""
    doc_tags = ["random", "unrelated"]
    assert security_policy.scope_allowed("public", doc_tags) is False


def test_support_scope_allows_support_tag(security_policy):
    """Test that support scope allows support-tagged documents."""
    doc_tags = ["support", "faq"]
    assert security_policy.scope_allowed("support", doc_tags) is True


def test_admin_scope_allows_internal(security_policy):
    """Test that admin scope allows internal documents."""
    doc_tags = ["internal", "faq"]
    assert security_policy.scope_allowed("admin", doc_tags) is True


def test_pii_denied_for_all_scopes(security_policy):
    """Test that PII is denied for all scopes."""
    doc_tags = ["faq", "pii"]

    assert security_policy.scope_allowed("public", doc_tags) is False
    assert security_policy.scope_allowed("support", doc_tags) is False
    assert security_policy.scope_allowed("admin", doc_tags) is False


def test_get_policy_hash(security_policy):
    """Test that policy hash is generated consistently."""
    hash1 = security_policy.get_policy_hash("public")
    hash2 = security_policy.get_policy_hash("public")

    assert hash1 == hash2
    assert len(hash1) == 8  # 8-character hash


def test_get_policy_hash_differs_by_scope(security_policy):
    """Test that different scopes have different hashes."""
    public_hash = security_policy.get_policy_hash("public")
    support_hash = security_policy.get_policy_hash("support")

    assert public_hash != support_hash


def test_validate_scope(security_policy):
    """Test scope validation."""
    assert security_policy.validate_scope("public") is True
    assert security_policy.validate_scope("support") is True
    assert security_policy.validate_scope("admin") is True
    assert security_policy.validate_scope("nonexistent") is False


def test_get_available_scopes(security_policy):
    """Test getting list of available scopes."""
    scopes = security_policy.get_available_scopes()

    assert "public" in scopes
    assert "support" in scopes
    assert "admin" in scopes


def test_get_allowed_tags(security_policy):
    """Test getting allowed tags for a scope."""
    allowed = security_policy.get_allowed_tags("public")

    assert "faq" in allowed
    assert "pricing" in allowed
    assert "features" in allowed
    assert "internal" not in allowed


def test_get_denied_tags(security_policy):
    """Test getting denied tags for a scope."""
    denied = security_policy.get_denied_tags("public")

    assert "internal" in denied
    assert "pii" in denied
