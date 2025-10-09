"""
Authentication and authorization middleware.
Supports API key authentication with scope-based access control.

For production: Replace in-memory storage with database.
"""

from fastapi import Depends, HTTPException, Security, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, List, Dict
import secrets
import hashlib
import json
from pathlib import Path
from app.config import PROJECT_ROOT

# Security scheme
security_scheme = HTTPBearer(auto_error=False)

# API Keys storage file
API_KEYS_FILE = PROJECT_ROOT / ".api_keys.json"


class User:
    """User with API key and scopes."""

    def __init__(self, user_id: str, scopes: List[str], api_key_hash: str):
        self.user_id = user_id
        self.scopes = scopes
        self.api_key_hash = api_key_hash

    def has_scope(self, scope: str) -> bool:
        """Check if user has access to scope."""
        return scope in self.scopes

    def to_dict(self) -> dict:
        """Serialize to dict."""
        return {
            "user_id": self.user_id,
            "scopes": self.scopes,
            "api_key_hash": self.api_key_hash
        }

    @staticmethod
    def from_dict(data: dict) -> 'User':
        """Deserialize from dict."""
        return User(
            user_id=data["user_id"],
            scopes=data["scopes"],
            api_key_hash=data["api_key_hash"]
        )


class APIKeyManager:
    """Manage API keys and user authentication."""

    def __init__(self):
        self.users: Dict[str, User] = {}
        self._load_keys()

    def _load_keys(self):
        """Load API keys from file."""
        if API_KEYS_FILE.exists():
            try:
                with open(API_KEYS_FILE, 'r') as f:
                    data = json.load(f)
                    for user_data in data.get("users", []):
                        user = User.from_dict(user_data)
                        # Store by hash for lookup
                        self.users[user.api_key_hash] = user
            except Exception as e:
                print(f"Warning: Could not load API keys: {e}")

    def _save_keys(self):
        """Save API keys to file."""
        data = {
            "users": [user.to_dict() for user in self.users.values()]
        }
        with open(API_KEYS_FILE, 'w') as f:
            json.dump(data, f, indent=2)

    @staticmethod
    def hash_api_key(api_key: str) -> str:
        """Hash API key for secure storage."""
        return hashlib.sha256(api_key.encode()).hexdigest()

    @staticmethod
    def generate_api_key() -> str:
        """Generate a secure random API key."""
        return secrets.token_urlsafe(32)

    def create_user(self, user_id: str, scopes: List[str]) -> str:
        """
        Create a new user with API key.

        Args:
            user_id: Unique user identifier
            scopes: List of allowed scopes (e.g., ["public", "support"])

        Returns:
            Generated API key (only returned once!)
        """
        # Generate API key
        api_key = self.generate_api_key()
        api_key_hash = self.hash_api_key(api_key)

        # Create user
        user = User(user_id=user_id, scopes=scopes, api_key_hash=api_key_hash)
        self.users[api_key_hash] = user

        # Save to file
        self._save_keys()

        return api_key

    def validate_api_key(self, api_key: str) -> Optional[User]:
        """
        Validate API key and return user.

        Args:
            api_key: API key to validate

        Returns:
            User if valid, None otherwise
        """
        api_key_hash = self.hash_api_key(api_key)
        return self.users.get(api_key_hash)

    def revoke_user(self, user_id: str) -> bool:
        """
        Revoke user's API key.

        Args:
            user_id: User to revoke

        Returns:
            True if revoked, False if not found
        """
        # Find user by user_id
        for api_key_hash, user in list(self.users.items()):
            if user.user_id == user_id:
                del self.users[api_key_hash]
                self._save_keys()
                return True
        return False

    def list_users(self) -> List[Dict]:
        """List all users (without API keys)."""
        return [
            {"user_id": user.user_id, "scopes": user.scopes}
            for user in self.users.values()
        ]


# Singleton instance
_api_key_manager: Optional[APIKeyManager] = None


def get_api_key_manager() -> APIKeyManager:
    """Get or create singleton APIKeyManager."""
    global _api_key_manager
    if _api_key_manager is None:
        _api_key_manager = APIKeyManager()
    return _api_key_manager


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Security(security_scheme)
) -> Optional[User]:
    """
    Dependency to extract and validate current user from API key.

    Returns None if no credentials (allows optional auth).
    Raises 401 if credentials provided but invalid.
    """
    # Import here to avoid circular dependency
    from app.audit import log_auth_attempt

    if credentials is None:
        return None

    # Extract token (API key)
    api_key = credentials.credentials

    # Validate
    manager = get_api_key_manager()
    user = manager.validate_api_key(api_key)

    if user is None:
        log_auth_attempt(success=False, reason="Invalid API key")
        raise HTTPException(
            status_code=401,
            detail="Invalid API key"
        )

    log_auth_attempt(success=True, user_id=user.user_id)
    return user


def require_auth(user: Optional[User] = Depends(get_current_user)) -> User:
    """
    Dependency that requires authentication.

    Use this when endpoint MUST have valid API key.
    """
    if user is None:
        raise HTTPException(
            status_code=401,
            detail="Authentication required. Provide API key in Authorization header."
        )
    return user


def require_scope(required_scope: str):
    """
    Dependency factory to check if user has required scope.

    Example:
        @app.post("/ask")
        async def ask(user: User = Depends(require_scope("support"))):
            ...
    """
    def scope_checker(user: User = Depends(require_auth)) -> User:
        if not user.has_scope(required_scope):
            raise HTTPException(
                status_code=403,
                detail=f"Access denied. Scope '{required_scope}' required."
            )
        return user

    return scope_checker
