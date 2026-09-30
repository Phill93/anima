"""
ChromaDB memory engine.

- Single collection for all memories, filtered by character_id.
- Persistent storage.
- Embeddings via a generic OpenAI-compatible HTTP endpoint (e.g. vLLM or
  Infinity serving BAAI/bge-m3). Configured through EMBED_BASE_URL / EMBED_MODEL
  / EMBED_API_KEY — no local model, no ~2.3 GB RAM per worker.

The client and collection are initialised lazily on first use, so importing
this module stays cheap. That matters for Gunicorn worker startup,
management commands and the test suite.
"""
import json
import logging
import os
import threading
import urllib.error
import urllib.request

import chromadb
from chromadb.utils import embedding_functions

logger = logging.getLogger(__name__)

# --- Embedding endpoint (generic OpenAI-compatible /embeddings API) ---
# Defaults to a local Infinity/vLLM instance; override per deployment.
EMBED_BASE_URL = os.environ.get("EMBED_BASE_URL", "http://127.0.0.1:7997")
EMBED_MODEL = os.environ.get("EMBED_MODEL", "BAAI/bge-m3")
EMBED_API_KEY = os.environ.get("EMBED_API_KEY", "")

# --- Chroma Client ---
# Pfad aus der Umgebung (Docker: /data/chroma), Default = lokaler Hermes-Ordner.
CHROMA_PATH = os.environ.get("CHROMA_PATH", os.path.expanduser("~/.hermes/chroma/anima"))

# --- Lazy singletons ---
# Initialisiert erst beim ersten echten Chroma-Zugriff (nicht beim Import).
_state = None
_lock = threading.Lock()


class OpenAICompatEmbeddingFunction(embedding_functions.EmbeddingFunction):
    """
    Embedding function that calls a generic OpenAI-compatible HTTP endpoint
    (POST /embeddings) instead of loading a local model.

    Works with vLLM, Infinity or any server that speaks the OpenAI embeddings
    API. No API key is sent when EMBED_API_KEY is empty.
    """

    def __init__(self, base_url: str = None, model: str = None, api_key: str = None):
        self.base_url = (base_url or EMBED_BASE_URL).rstrip("/")
        self.model = model or EMBED_MODEL
        self.api_key = api_key if api_key is not None else EMBED_API_KEY

    def __call__(self, input):
        """Embed one or more texts via the /embeddings endpoint."""
        payload = json.dumps({"model": self.model, "input": input}).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        req = urllib.request.Request(
            f"{self.base_url}/embeddings",
            data=payload,
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        # OpenAI shape: {"data": [{"embedding": [...], "index": N}, ...]}
        entries = sorted(data.get("data", []), key=lambda e: e.get("index", 0))
        return [e["embedding"] for e in entries]

    def name(self) -> str:
        return "openai_compat"

    def get_config(self) -> dict:
        return {"base_url": self.base_url, "model": self.model, "api_key": self.api_key}

    @classmethod
    def build_from_config(cls, config: dict):
        return cls(**config)


def _get_state():
    """Create (once) and return the shared client, ef, collection."""
    global _state
    if _state is not None:
        return _state
    with _lock:
        if _state is not None:
            return _state
        logger.info("Initialising Chroma at %s (embeddings: %s, model: %s)",
                    CHROMA_PATH, EMBED_BASE_URL, EMBED_MODEL)
        os.makedirs(CHROMA_PATH, exist_ok=True)
        client = chromadb.PersistentClient(path=CHROMA_PATH)
        ef = OpenAICompatEmbeddingFunction()
        collection = client.get_or_create_collection(
            name="memories",
            metadata={"hnsw:space": "cosine"},
            embedding_function=ef,
        )
        _state = {"client": client, "ef": ef, "collection": collection}
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
# Exported to be shared across the application without re-initialising the
# client. Construction is cheap; the connection is only established on the
# first Chroma operation.
memory_engine = MemoryEngine()
