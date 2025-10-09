"""
RBAC policy enforcement and security controls.
Deterministic access control based on scope and document tags.
"""

import hashlib
import json
from typing import List, Set, Dict, Any
from app.config import load_privilege_map


class SecurityPolicy:
    """Manages RBAC policies and access control."""

    def __init__(self):
        """Initialize with privilege map from corpus."""
        self.privilege_map: Dict[str, Any] = load_privilege_map()
        self._policy_hash_cache: Dict[str, str] = {}

    def reload_policies(self) -> None:
        """Reload privilege map from disk (for live updates)."""
        self.privilege_map = load_privilege_map()
        self._policy_hash_cache.clear()

    def scope_allowed(self, scope: str, doc_tags: List[str]) -> bool:
        """
        Check if a scope is allowed to access a document based on tags.

        Args:
            scope: RBAC scope (e.g., 'public', 'support', 'admin')
            doc_tags: List of tags attached to document

        Returns:
            True if access allowed, False otherwise
        """
        scope_policy = self.privilege_map.get(scope, {})
        allowed_tags = set(scope_policy.get("allowed_tags", []))
        deny_tags = set(scope_policy.get("deny", []))
        doc_tag_set = set(doc_tags)

        # Must have at least one allowed tag AND no deny tags
        has_allowed = len(doc_tag_set & allowed_tags) > 0
        has_denied = len(doc_tag_set & deny_tags) > 0

        return has_allowed and not has_denied

    def get_allowed_tags(self, scope: str) -> Set[str]:
        """Get set of allowed tags for a scope."""
        scope_policy = self.privilege_map.get(scope, {})
        return set(scope_policy.get("allowed_tags", []))

    def get_denied_tags(self, scope: str) -> Set[str]:
        """Get set of denied tags for a scope."""
        scope_policy = self.privilege_map.get(scope, {})
        return set(scope_policy.get("deny", []))

    def get_policy_hash(self, scope: str) -> str:
        """
        Generate deterministic hash of scope policy.
        Useful for audit trails and tamper detection.

        Args:
            scope: RBAC scope

        Returns:
            8-character hex hash of policy
        """
        if scope in self._policy_hash_cache:
            return self._policy_hash_cache[scope]

        scope_policy = self.privilege_map.get(scope, {})
        policy_json = json.dumps(scope_policy, sort_keys=True)
        policy_hash = hashlib.sha256(policy_json.encode()).hexdigest()[:8]

        self._policy_hash_cache[scope] = policy_hash
        return policy_hash

    def validate_scope(self, scope: str) -> bool:
        """Check if a scope exists in privilege map."""
        return scope in self.privilege_map

    def get_available_scopes(self) -> List[str]:
        """Get list of all available scopes."""
        return list(self.privilege_map.keys())


# Singleton instance
_security_policy: SecurityPolicy | None = None


def get_security_policy() -> SecurityPolicy:
    """Get or create singleton SecurityPolicy instance."""
    global _security_policy
    if _security_policy is None:
        _security_policy = SecurityPolicy()
    return _security_policy
