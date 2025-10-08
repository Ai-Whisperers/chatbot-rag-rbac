"""
Vector store and embedding management.
Handles document storage, retrieval, and similarity search.
"""

import chromadb
from chromadb.utils import embedding_functions
from chromadb.config import Settings
from typing import List, Dict, Any, Tuple
from functools import lru_cache
from app.config import (
    CHROMA_PERSIST_DIR,
    COLLECTION_NAME,
    EMBED_MODEL,
    TOP_K,
    SIMILARITY_THRESHOLD,
    EMBEDDING_CACHE_SIZE
)


class VectorStore:
    """Manages vector storage and retrieval operations."""

    def __init__(self):
        """Initialize ChromaDB client and collection."""
        self.client = chromadb.Client(Settings(
            persist_directory=CHROMA_PERSIST_DIR,
            anonymized_telemetry=False
        ))

        # Initialize embedding function
        self.embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=EMBED_MODEL
        )

        # Get or create collection
        try:
            self.collection = self.client.get_collection(
                name=COLLECTION_NAME,
                embedding_function=self.embedding_function
            )
        except Exception:
            self.collection = self.client.create_collection(
                name=COLLECTION_NAME,
                embedding_function=self.embedding_function,
                metadata={"hnsw:space": "cosine"}  # Use cosine similarity
            )

    def upsert(self, doc_id: str, text: str, tags: List[str], metadata: Dict[str, Any] | None = None) -> None:
        """
        Upsert a document into the vector store.

        Args:
            doc_id: Unique document identifier
            text: Document content
            tags: Access control tags
            metadata: Additional metadata
        """
        meta = metadata or {}
        meta["tags"] = tags  # Always include tags in metadata

        self.collection.upsert(
            ids=[doc_id],
            documents=[text],
            metadatas=[meta]
        )

    def batch_upsert(self, documents: List[Tuple[str, str, List[str], Dict[str, Any] | None]]) -> None:
        """
        Batch upsert multiple documents.

        Args:
            documents: List of (doc_id, text, tags, metadata) tuples
        """
        if not documents:
            return

        ids = []
        texts = []
        metadatas = []

        for doc_id, text, tags, metadata in documents:
            meta = metadata or {}
            meta["tags"] = tags

            ids.append(doc_id)
            texts.append(text)
            metadatas.append(meta)

        self.collection.upsert(
            ids=ids,
            documents=texts,
            metadatas=metadatas
        )

    def query(
        self,
        query_text: str,
        n_results: int = TOP_K
    ) -> Tuple[List[str], List[Dict[str, Any]], List[float]]:
        """
        Query vector store for similar documents.

        Args:
            query_text: Query string
            n_results: Number of results to return

        Returns:
            Tuple of (documents, metadatas, distances)
        """
        results = self.collection.query(
            query_texts=[query_text],
            n_results=n_results,
            include=["documents", "metadatas", "distances"]
        )

        documents = results["documents"][0] if results["documents"] else []
        metadatas = results["metadatas"][0] if results["metadatas"] else []
        distances = results["distances"][0] if results["distances"] else []

        return documents, metadatas, distances

    def delete(self, doc_id: str) -> None:
        """Delete a document by ID."""
        self.collection.delete(ids=[doc_id])

    def count(self) -> int:
        """Get total document count in collection."""
        return self.collection.count()

    def get_all_tags(self) -> List[str]:
        """Extract all unique tags from collection metadata."""
        # Note: Chroma doesn't have a direct way to get all unique metadata values
        # This is a placeholder - in production, maintain a separate tags index
        all_docs = self.collection.get()
        tags = set()

        if all_docs and all_docs.get("metadatas"):
            for meta in all_docs["metadatas"]:
                if meta and "tags" in meta:
                    tags.update(meta["tags"])

        return sorted(list(tags))

    @staticmethod
    def distance_to_similarity(distance: float) -> float:
        """
        Convert Chroma distance to similarity score.
        Chroma uses L2 distance, smaller = more similar.

        Args:
            distance: L2 distance from Chroma

        Returns:
            Similarity score between 0 and 1
        """
        # Simple conversion: similarity = 1 / (1 + distance)
        # This maps distance [0, inf) to similarity [1, 0)
        return 1.0 / (1.0 + distance)


# Singleton instance
_vector_store: VectorStore | None = None


def get_vector_store() -> VectorStore:
    """Get or create singleton VectorStore instance."""
    global _vector_store
    if _vector_store is None:
        _vector_store = VectorStore()
    return _vector_store


@lru_cache(maxsize=EMBEDDING_CACHE_SIZE)
def cached_query(query_text: str, n_results: int = TOP_K) -> str:
    """
    Cached wrapper for queries (for frequently asked questions).
    Returns JSON string to make it hashable for lru_cache.
    """
    import json
    store = get_vector_store()
    docs, metas, dists = store.query(query_text, n_results)

    result = {
        "documents": docs,
        "metadatas": metas,
        "distances": dists
    }

    return json.dumps(result)
