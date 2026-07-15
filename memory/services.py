"""
ChromaDB memory engine.

- Single collection for all memories, filtered by character_id.
- Persistent storage.
- BGE-m3 embedding function.
"""
import os
from sentence_transformers import SentenceTransformer
import chromadb
from chromadb.utils import embedding_functions

# --- Chroma Client ---
CHROMA_PATH = os.path.expanduser("~/.hermes/chroma/anima")
client = chromadb.PersistentClient(path=CHROMA_PATH)

# Single collection for all memories
collection = client.get_or_create_collection(
    name="memories",
    metadata={"hnsw:space": "cosine"},
)


def get_ef():
    """
    Return the embedding function for BGE-m3.
    We use the built-in Chroma helper to ensure compatibility with the 
    collection's internal encoding.
    """
    return embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="BAAI/bge-m3"
    )


class MemoryEngine:
    """Thin wrapper around Chroma for our memory needs."""

    def __init__(self):
        self.ef = get_ef()
        self.collection = collection

    # --- Core ---

    def add(self, character_id: int, text: str, memory_type: str, score: float = 1.0, embedding_id: str = "") -> str:
        """
        Add a memory to Chroma.
        Returns the generated Chroma ID.
        """
        existing = self.collection.get(
            where={"character_id": str(character_id), "embedding_id": embedding_id},
            include=["metadatas"],
        )
        if existing["ids"]:
            # Avoid duplicate embedding_id inserts
            return existing["ids"][0]

        doc_id = f"char_{character_id}_{embedding_id or text[:20]}"
        metadata = {
            "character_id": str(character_id),
            "memory_type": memory_type,
            "score": score,
            "embedding_id": embedding_id,
        }
        self.collection.add(
            ids=[doc_id],
            documents=[text],
            metadatas=[metadata],
        )
        return doc_id

    def query(self, character_id: int, query_text: str, n_results: int = 3, memory_type: str = None) -> dict:
        """
        Semantic search for memories of a specific character.
        """
        where = {"character_id": str(character_id)}
        if memory_type:
            where["memory_type"] = memory_type

        result = self.collection.query(
            query_texts=[query_text],
            n_results=n_results,
            where=where,
        )
        return result

    def get_all(self, character_id: int) -> dict:
        """Get all memories for a character."""
        return self.collection.get(
            where={"character_id": str(character_id)},
            include=["documents", "metadatas"],
        )

    def delete(self, doc_id: str) -> bool:
        """Delete a memory by Chroma ID."""
        self.collection.delete(ids=[doc_id])
        return True

    def count(self, character_id: int) -> int:
        """Count memories for a character."""
        result = self.collection.get(
            where={"character_id": str(character_id)}
        )
        return len(result["ids"])
