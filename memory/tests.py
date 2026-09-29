"""
Tests for the memory app: MemoryRetriever (dedup, scoring, retrieval,
archival) and the Memory model.

Chroma is mocked via conftest.py; the memory_engine is a MagicMock here.
"""
import pytest
from unittest.mock import MagicMock, patch

from characters.models import Character
from memory.models import Memory, MemoryType
from memory.retriever import (
    MemoryRetriever,
    MAX_MEMORIES_PER_CHARACTER,
)


@pytest.fixture
def retriever():
    """A retriever with the memory_engine mocked out."""
    r = MemoryRetriever()
    r.engine = MagicMock()
    r.engine.count.return_value = 0
    r.engine.get_similar.return_value = []
    return r


def _make_memory(c, text, mem_type="fact", score=1.0,
                 embedding_id="emb-1", is_archived=False):
    return Memory.objects.create(
        character=c,
        memory_type=mem_type,
        text=text,
        embedding_id=embedding_id,
        score=score,
        is_archived=is_archived,
    )


# ---------------------------------------------------------------------------
# Memory model
# ---------------------------------------------------------------------------

class TestMemoryModel:
    def test_defaults(self, db):
        c = Character.objects.create(name="Kaya", description="")
        m = Memory.objects.create(
            character=c, memory_type=MemoryType.FACT, text="Kaya loves fish."
        )
        assert m.score == 1.0
        assert m.is_archived is False
        assert m.session_count == 0
        assert m.embedding_id == ""

    def test_str(self, db):
        c = Character.objects.create(name="Kaya", description="")
        m = Memory.objects.create(
            character=c, memory_type=MemoryType.FACT, text="Kaya loves fish."
        )
        assert "Fact" in str(m)
        assert "Kaya loves fish" in str(m)

    def test_type_choices(self):
        valid = [t[0] for t in MemoryType.choices]
        assert "fact" in valid
        assert "event" in valid
        assert "emotion" in valid
        assert "relationship" in valid
        assert "preference" in valid


# ---------------------------------------------------------------------------
# MemoryRetriever.add_memory
# ---------------------------------------------------------------------------

class TestAddMemory:
    def test_add_creates_memory_and_calls_engine(self, db, retriever):
        """add_memory() persists the Memory and calls engine.add()."""
        c = Character.objects.create(name="Kaya", description="")
        retriever.engine.add = MagicMock(return_value="emb-123")

        mem = retriever.add_memory(
            character=c, text="Kaya loves fish.", memory_type="fact"
        )
        assert mem.pk is not None
        assert mem.embedding_id == "emb-123"
        retriever.engine.add.assert_called_once()

    def test_initial_score_by_type(self, db, retriever):
        """Initial score depends on the memory type."""
        c = Character.objects.create(name="Kaya", description="")
        retriever.engine.add = MagicMock(return_value="e1")
        mem = retriever.add_memory(
            character=c, text="fact text", memory_type="fact"
        )
        assert mem.score == 2.0

    def test_initial_score_event(self, db, retriever):
        c = Character.objects.create(name="Kaya", description="")
        retriever.engine.add = MagicMock(return_value="e2")
        mem = retriever.add_memory(
            character=c, text="event text", memory_type="event"
        )
        assert mem.score == 1.5

    def test_initial_score_relationship(self, db, retriever):
        c = Character.objects.create(name="Kaya", description="")
        retriever.engine.add = MagicMock(return_value="e3")
        mem = retriever.add_memory(
            character=c, text="rel text", memory_type="relationship"
        )
        assert mem.score == 2.5

    def test_dedup_same_embedding_id_returns_none(self, db, retriever):
        """A duplicate embedding_id (active memory) is not stored again."""
        c = Character.objects.create(name="Kaya", description="")
        _make_memory(c, "existing.", "fact", embedding_id="dup-1")
        retriever.engine.add = MagicMock()

        result = retriever.add_memory(
            character=c, text="new text", memory_type="fact",
            embedding_id="dup-1",
        )
        assert result is None
        retriever.engine.add.assert_not_called()
        assert Memory.objects.count() == 1

    def test_no_dedup_check_without_embedding_id(self, db, retriever):
        """Without embedding_id no dedup is done, a new row is created."""
        c = Character.objects.create(name="Kaya", description="")
        retriever.engine.add = MagicMock(return_value="new-emb")
        result = retriever.add_memory(
            character=c, text="x", memory_type="fact"
        )
        assert result is not None
        assert Memory.objects.count() == 1

    def test_archive_triggered_over_limit(self, db, retriever):
        """When the engine count exceeds the cap, the oldest are archived."""
        c = Character.objects.create(name="Kaya", description="")
        # Simulate: engine already at the limit
        retriever.engine.add = MagicMock(return_value="new-emb")
        retriever.engine.count = MagicMock(
            return_value=MAX_MEMORIES_PER_CHARACTER + 2
        )
        # Pre-create the "oldest" memories that should be archived
        old1 = _make_memory(c, "oldest.", "fact", embedding_id="old-1", score=0.5)
        old2 = _make_memory(c, "old.", "fact", embedding_id="old-2", score=0.9)

        retriever.add_memory(
            character=c, text="new text", memory_type="fact"
        )

        old1.refresh_from_db()
        old2.refresh_from_db()
        assert old1.is_archived is True
        # 2 memories should be archived (count - MAX = 2)
        assert Memory.objects.filter(is_archived=True).count() == 2

    def test_no_archive_under_limit(self, db, retriever):
        """Nothing is archived when the count is at or below the cap."""
        c = Character.objects.create(name="Kaya", description="")
        retriever.engine.add = MagicMock(return_value="e1")
        retriever.engine.count = MagicMock(
            return_value=MAX_MEMORIES_PER_CHARACTER
        )
        _make_memory(c, "stays.", "fact", embedding_id="k1", score=0.1)
        retriever.add_memory(character=c, text="x", memory_type="fact")
        assert Memory.objects.filter(is_archived=True).count() == 0


# ---------------------------------------------------------------------------
# MemoryRetriever.retrieve
# ---------------------------------------------------------------------------

def _chroma_result(texts, metas=None, ids=None):
    """Build a Chroma-style result dict."""
    n = len(texts)
    return {
        "ids": [ids if ids else [f"id-{i}" for i in range(n)]],
        "metadatas": [metas if metas else [
            {"text": t, "memory_type": "fact", "character_id": 1}
            for t in texts
        ]],
        "documents": [texts],
        "embeddings": None,
        "distances": [[0.1 * (i + 1) for i in range(n)]],
    }


class TestRetrieve:
    def test_passes_chroma_results_through(self, db, retriever):
        """Chroma results are returned (unchanged when no keyword match)."""
        c = Character.objects.create(name="Kaya", description="")
        retriever.engine.query = MagicMock(
            return_value=_chroma_result(["alpha.", "beta."])
        )
        result = retriever.retrieve(c, "something else", n_results=3)
        # no keyword "something" in either doc → docs unchanged
        assert result["documents"][0] == ["alpha.", "beta."]

    def test_keyword_match_gets_boosted_first(self, db, retriever):
        """Docs containing the first query word are placed first."""
        c = Character.objects.create(name="Kaya", description="")
        retriever.engine.query = MagicMock(
            return_value=_chroma_result(["apple pie.", "banana bread."])
        )
        result = retriever.retrieve(c, "apple tart", n_results=2)
        # "apple" is in the first word of the query → "apple pie." first
        assert result["documents"][0][0] == "apple pie."

    def test_n_results_respected(self, db, retriever):
        """Only n_results docs are returned."""
        c = Character.objects.create(name="Kaya", description="")
        retriever.engine.query = MagicMock(
            return_value=_chroma_result(
                ["one.", "two.", "three.", "four.", "five.", "six."]
            )
        )
        result = retriever.retrieve(c, "query", n_results=3)
        assert len(result["documents"][0]) == 3

    def test_candidate_count_is_n_times_3(self, db, retriever):
        """The engine is queried with n_results * 3 candidates."""
        c = Character.objects.create(name="Kaya", description="")
        retriever.engine.query = MagicMock(return_value={})
        retriever.retrieve(c, "query", n_results=5)
        # engine.query(character_id, query, candidate_count, memory_type)
        args = retriever.engine.query.call_args[0]
        assert args[2] == 15

    def test_empty_result_returns_empty(self, db, retriever):
        """An empty Chroma result is returned as-is (no crash)."""
        c = Character.objects.create(name="Kaya", description="")
        retriever.engine.query = MagicMock(return_value={"documents": []})
        result = retriever.retrieve(c, "anything", n_results=3)
        assert result["documents"] == []

    def test_memory_type_filter_passed_through(self, db, retriever):
        """A memory_type filter is forwarded to the engine."""
        c = Character.objects.create(name="Kaya", description="")
        retriever.engine.query = MagicMock(return_value={})
        retriever.retrieve(c, "q", n_results=2, memory_type="event")
        args = retriever.engine.query.call_args[0]
        assert args[3] == "event"


# ---------------------------------------------------------------------------
# MemoryRetriever.archive_oldest
# ---------------------------------------------------------------------------

class TestArchiveOldest:
    def test_archives_lowest_scores(self, db, retriever):
        """The least important (lowest score) memories are archived."""
        c = Character.objects.create(name="Kaya", description="")
        m_low = _make_memory(c, "low score.", "fact", embedding_id="low", score=0.1)
        _make_memory(c, "mid score.", "fact", embedding_id="mid", score=0.8)
        retriever.engine.delete = MagicMock()

        retriever.archive_oldest(c, count=1)

        m_low.refresh_from_db()
        assert m_low.is_archived is True
        retriever.engine.delete.assert_called_once_with("low")

    def test_multiple_archived(self, db, retriever):
        """count=2 archives the two lowest scores."""
        c = Character.objects.create(name="Kaya", description="")
        _make_memory(c, "a.", "fact", embedding_id="a", score=0.1)
        _make_memory(c, "b.", "fact", embedding_id="b", score=0.5)
        _make_memory(c, "c.", "fact", embedding_id="c", score=0.9)
        retriever.engine.delete = MagicMock()

        retriever.archive_oldest(c, count=2)

        assert Memory.objects.filter(is_archived=True).count() == 2
        assert set(retriever.engine.delete.call_args_list[0][0]) is not None
        deleted = [call[0][0] for call in retriever.engine.delete.call_args_list]
        assert set(deleted) == {"a", "b"}

    def test_noop_when_count_zero(self, db, retriever):
        """count=0 does nothing."""
        c = Character.objects.create(name="Kaya", description="")
        _make_memory(c, "x.", "fact", embedding_id="x", score=0.1)
        retriever.engine.delete = MagicMock()
        retriever.archive_oldest(c, count=0)
        assert Memory.objects.filter(is_archived=True).count() == 0
        retriever.engine.delete.assert_not_called()
