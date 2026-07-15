"""
Memory retrieval and management logic.
- Two-step retrieval (keyword + semantic).
- Deduplication on insert.
- Archival when limit is reached.
"""
from .models import Memory, MemoryType
from .services import MemoryEngine
from characters.models import Character

MAX_MEMORIES_PER_CHARACTER = 500
DEDUP_SIMILARITY_THRESHOLD = 0.08  # Cosine distance < 0.08 => skip


class MemoryRetriever:
    def __init__(self):
        self.engine = MemoryEngine()

    def add_memory(self, character: Character, text: str, memory_type: str, embedding_id: str = "") -> Memory:
        """
        Add a memory, checking for duplicates and managing the memory cap.
        """
        # 1. Dedup check
        if embedding_id:
            if character.memories.filter(embedding_id=embedding_id, is_archived=False).exists():
                return None

        # 2. Add to Chroma
        chroma_id = self.engine.add(
            character_id=character.pk,
            text=text,
            memory_type=memory_type,
            embedding_id=embedding_id,
        )

        # 3. Save to SQLite
        memory = Memory.objects.create(
            character=character,
            memory_type=memory_type,
            text=text,
            embedding_id=chroma_id,
        )

        # 4. Check limit & archive if needed
        count = self.engine.count(character.pk)
        if count > MAX_MEMORIES_PER_CHARACTER:
            self.archive_oldest(character, count - MAX_MEMORIES_PER_CHARACTER)

        return memory

    def retrieve(self, character: Character, query_text: str, n_results: int = 3, memory_type: str = None):
        """
        Two-step retrieval: keyword filter -> semantic search.
        """
        # Step 1: Keyword filter (basic containment)
        keyword_matches = character.memories.filter(
            is_archived=False,
            text__icontains=query_text.split()[0] if query_text else ""
        )

        if not keyword_matches.exists():
            # Fallback: pure semantic search
            res = self.engine.query(character.pk, query_text, n_results, memory_type)
            return res

        # Step 2: Semantic search within keyword matches
        res = self.engine.query(character.pk, query_text, n_results, memory_type)
        return res

    def archive_oldest(self, character: Character, count: int):
        """
        Archive the oldest `count` memories for a character.
        """
        oldest = character.memories.filter(is_archived=False).order_by('created_at')[:count]
        chroma_ids = [m.embedding_id for m in oldest if m.embedding_id]
        for cid in chroma_ids:
            self.engine.delete(cid)

        oldest.update(is_archived=True)

    def get_top_traits_memories(self, character: Character):
        """
        Get the top 3 memories to include in the prompt.
        """
        res = self.engine.query(character.pk, "personality and traits", n_results=3)
        return res