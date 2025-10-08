"""
Centralized configuration management.
All environment variables and constants defined here for portability.
"""

import os
import json
from pathlib import Path
from typing import Dict, Any

# ==================== PATHS ====================
# Resolve paths relative to project root, not this file
PROJECT_ROOT = Path(__file__).parent.parent.absolute()
CORPUS_DIR = PROJECT_ROOT / "corpus"
CORPUS_DOCS_DIR = CORPUS_DIR / "docs"
PRIVILEGE_MAP_PATH = CORPUS_DIR / "privilege_map.json"
METADATA_PATH = CORPUS_DIR / "metadata.json"

# ==================== LLM CONFIG ====================
MODEL_ENDPOINT = os.getenv("OLLAMA_ENDPOINT", "http://localhost:11434")
MODEL_NAME = os.getenv("MODEL_NAME", "qwen2.5:3b-instruct")

# LLM Generation Parameters (deterministic)
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.0"))
TOP_P = float(os.getenv("TOP_P", "1.0"))
TOP_K_SAMPLING = int(os.getenv("TOP_K_SAMPLING", "1"))
REPEAT_PENALTY = float(os.getenv("REPEAT_PENALTY", "1.0"))
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "384"))

# ==================== EMBEDDING CONFIG ====================
EMBED_MODEL = os.getenv("EMBED_MODEL", "all-MiniLM-L6-v2")
EMBEDDING_CACHE_SIZE = int(os.getenv("EMBEDDING_CACHE_SIZE", "1000"))

# ==================== RETRIEVAL CONFIG ====================
TOP_K = int(os.getenv("TOP_K", "4"))
SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.75"))

# ==================== VECTOR STORE CONFIG ====================
VECTOR_STORE_TYPE = os.getenv("VECTOR_STORE_TYPE", "chroma")  # chroma | qdrant
CHROMA_PERSIST_DIR = os.getenv("CHROMA_PERSIST_DIR", str(PROJECT_ROOT / ".chroma"))
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "faq")

# ==================== API CONFIG ====================
API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))
API_WORKERS = int(os.getenv("API_WORKERS", "1"))

# ==================== SECURITY CONFIG ====================
ENABLE_CORS = os.getenv("ENABLE_CORS", "true").lower() == "true"
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*").split(",")

# ==================== LOGGING ====================
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# ==================== PRIVILEGE MAP ====================
def load_privilege_map() -> Dict[str, Any]:
    """Load RBAC privilege map from corpus directory."""
    if PRIVILEGE_MAP_PATH.exists():
        with open(PRIVILEGE_MAP_PATH, "r", encoding="utf-8") as f:
            return json.load(f)

    # Fallback default if not found
    return {
        "public": {
            "allowed_tags": ["faq", "pricing", "features"],
            "deny": ["internal", "pii"]
        },
        "support": {
            "allowed_tags": ["faq", "pricing", "features", "support"],
            "deny": ["internal", "pii"]
        },
        "admin": {
            "allowed_tags": ["faq", "pricing", "features", "support", "internal"],
            "deny": ["pii"]
        }
    }

# ==================== REFUSAL MESSAGE ====================
REFUSAL_MESSAGE = "I don't have that information."

# ==================== VALIDATION ====================
def validate_config() -> None:
    """Validate critical configuration on startup."""
    errors = []

    if not CORPUS_DIR.exists():
        errors.append(f"Corpus directory not found: {CORPUS_DIR}")

    if not CORPUS_DOCS_DIR.exists():
        errors.append(f"Corpus docs directory not found: {CORPUS_DOCS_DIR}")

    if TEMPERATURE != 0.0:
        print(f"⚠️  Warning: TEMPERATURE={TEMPERATURE} (non-deterministic mode)")

    if SIMILARITY_THRESHOLD < 0.5:
        print(f"⚠️  Warning: SIMILARITY_THRESHOLD={SIMILARITY_THRESHOLD} (low threshold may reduce accuracy)")

    if errors:
        raise ValueError(f"Configuration errors:\n" + "\n".join(f"  - {e}" for e in errors))

    print(f"✓ Configuration validated")
    print(f"  - Corpus: {CORPUS_DIR}")
    print(f"  - Model: {MODEL_NAME}")
    print(f"  - Embedding: {EMBED_MODEL}")
    print(f"  - Similarity threshold: {SIMILARITY_THRESHOLD}")
