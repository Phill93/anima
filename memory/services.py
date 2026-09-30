"""
ChromaDB memory engine.

- Single collection for all memories, filtered by character_id.
- Persistent storage.
- BGE-m3 embedding function (Cached/Singleton for performance).

The model and collection are initialised lazily on first use, so importing
this module stays cheap. That matters for Gunicorn worker startup,
management commands and the test suite — none of them should pay the
~2.3 GB model cost just by importing.
"""
import logging
import os
import threading

import chromadb
from chromadb.utils import embedding_functions
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

# --- Chroma Client ---
# Pfad aus der Umgebung (Docker: /data/chroma), Default = lokaler Hermes-Ordner.
CHROMA_PATH = os.environ.get("CHROMA_PATH", os.path.expanduser("~/.hermes/chroma/anima"))

# --- Lazy singletons ---
# Initialisiert erst beim ersten echten Chroma-Zugriff (nicht beim Import).
_state = None
_lock = threading.Lock()


def _get_state():
    """Create (once) and return the shared client, model, ef, collection."""
    global _state
    if _state is not None:
        return _state
    with _lock:
        if _state is not None:
            return _state
        model_name = os.environ.get("EMBED_MODEL", "BAAI/bge-m3")
        logger.info("Initialising Chroma at %s (model: %s)", CHROMA_PATH, model_name)
        os.makedirs(CHROMA_PATH, exist_ok=True)
        client = chromadb.PersistentClient(path=CHROMA_PATH)
        model = SentenceTransformer(model_name)
        ef = embedding_functions.SentenceTransformerEmbeddingFunction(model_name=model_name)
        collection = client.get_or_create_collection(
            name="memories",
            metadata={"hnsw:space": "cosine"},
            embedding_function=ef,
        )
        _state = {"client": client, "model": model, "ef": ef, "collection": collection}
    return _state


class MemoryEngine:
    """Thin wrapper around Chroma for our memory needs."""

    # --- Core ---

    def add(self, character_id: int, text: str, memory_type: str, score: float = 1.0, embedding_id: str = "") -> str:
        """
        Add a memory to Chroma.
        Returns the generated Chroma ID.
        """
        self._collection()

        # Dedup check
        existing = self._collection().get(
            where={"character_id": str(character_id)},
            include=["metadatas"],
        )
        if existing["ids"]:
            for meta, doc_id in zip(existing["metadatas"], existing["ids"]):
                if meta.get("embedding_id") == embedding_id:
                    return doc_id

        doc_id = f"char_{character_id}_{embedding_id or text[:20]}"
        metadata = {
            "character_id": str(character_id),
            "memory_type": memory_type,
            "score": score,
            "embedding_id": embedding_id,
        }
        self._collection().add(
            ids=[doc_id],
            documents=[text],
            metadatas=[metadata],
        )
        return doc_id

    def query(self, character_id: int, query_text: str, n_results: int = 3, memory_type: str = None) -> dict:
        """
        Semantic search for memories of a specific character.
        """
        char_id_str = str(character_id)
        where = {"character_id": char_id_str}
        if memory_type:
            where["$and"] = [{"character_id": char_id_str}, {"memory_type": memory_type}]

        result = self._collection().query(
            query_texts=[query_text],
            n_results=n_results,
            where=where,
            include=["documents", "metadatas", "distances"],
        )
        return result

    def get_all(self, character_id: int) -> dict:
        """Get all memories for a character."""
        return self._collection().get(
            where={"character_id": str(character_id)},
            include=["documents", "metadatas"],
        )

    def delete(self, doc_id: str) -> bool:
        """Delete a memory by Chroma ID."""
        if not doc_id:
            return False
        self._collection().delete(ids=[doc_id])
        return True

    def count(self, character_id: int) -> int:
        """Count memories for a character."""
        result = self._collection().get(
            where={"character_id": str(character_id)}
        )
        return len(result["ids"])

    # --- Lazy initialisation helper ---

    def _collection(self):
        """Return the (lazily initialised) collection."""
        return _get_state()["collection"]


# --- Singleton Instance ---
# Exported to be shared across the application without re-initializing the model.
# Construction is cheap; the model is only loaded on the first Chroma operation.
memory_engine = MemoryEngine()
