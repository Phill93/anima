"""
Tests for web views: chat flow, character/trait/world management.

All LLM calls and the Chroma engine are mocked; requests use JSON bodies.
"""
import json
import pytest
from unittest.mock import MagicMock, patch
from django.test import Client

from characters.models import Character, Trait, GlobalConfig
from worlds.models import World, Location
from anima_sessions.models import Session, SessionTurn
from memory.models import Memory


@pytest.fixture
def client():
    return Client()


@pytest.fixture
def character(db):
    return Character.objects.create(
        name="Rex", description="A dragon",
        personality={"voice": "gruff", "quirks": "hoards coins"},
    )


@pytest.fixture
def world(db, character):
    w = World.objects.create(
        name="Ardania", description="A fantasy world",
        rules="No flying.",
        lore=[{"name": "History", "content": "Ancient magic."}],
    )
    Location.objects.create(world=w, name="Cave", description="A dark cave.")
    character.world = w
    character.save()
    return w


def _post(client, url, data):
    """POST a JSON body to a URL."""
    return client.post(
        url,
        data=json.dumps(data),
        content_type="application/json",
    )


# ---------------------------------------------------------------------------
# Index
# ---------------------------------------------------------------------------

class TestIndex:
    def test_no_characters(self, client, db):
        resp = client.get("/")
        assert resp.status_code == 200

    def test_with_character(self, client, character):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "Rex" in resp.content.decode()


# ---------------------------------------------------------------------------
# Chat flow
# ---------------------------------------------------------------------------

class TestChatInit:
    def test_creates_session(self, client, character, db):
        resp = _post(client, "/chat/init/", {"character_id": character.pk})
        assert resp.status_code == 200
        data = resp.json()
        assert data["character_name"] == "Rex"
        assert Session.objects.count() == 1
        s = Session.objects.first()
        assert s.pk == data["session_id"]
        assert s.turn_count == 0

    def test_missing_character_id(self, client, db):
        resp = _post(client, "/chat/init/", {})
        assert resp.status_code == 400

    def test_unknown_character(self, client, db):
        resp = _post(client, "/chat/init/", {"character_id": 9999})
        assert resp.status_code == 404

    def test_get_not_allowed(self, client, db):
        resp = client.get("/chat/init/")
        assert resp.status_code == 405


class TestChatSend:
    def test_full_turn(self, client, character, db):
        """A full chat turn: LLM response, turn saved, memory added."""
        with patch("web.views.MemoryRetriever") as mock_cls:
            mock_retriever = MagicMock()
            mock_cls.return_value = mock_retriever
            mock_retriever.retrieve.return_value = {"documents": [["fish."]]}
            mock_retriever.add_memory = MagicMock()

            session = Session.objects.create(character=character, turn_count=0)
            with patch("web.views.LLMClient") as mock_llm_cls:
                mock_llm = MagicMock()
                mock_llm.generate.return_value = "TEST_REPLY"
                mock_llm_cls.return_value = mock_llm
                resp = _post(client, "/chat/send/", {
                    "session_id": session.pk,
                    "message": "Hello Rex!",
                })
        assert resp.status_code == 200
        data = resp.json()
        assert data["response"] == "TEST_REPLY"
        assert data["turn_number"] == 1
        session.refresh_from_db()
        assert session.turn_count == 1
        assert session.turns.count() == 1
        turn = session.turns.first()
        assert turn.user_message == "Hello Rex!"
        assert turn.character_response == "TEST_REPLY"
        # memory was written
        mock_retriever.add_memory.assert_called_once()
        assert mock_retriever.add_memory.call_args[1]["memory_type"] == "event"

    def test_missing_message(self, client, character, db):
        session = Session.objects.create(character=character, turn_count=0)
        resp = _post(client, "/chat/send/", {"session_id": session.pk})
        assert resp.status_code == 400

    def test_missing_session_id(self, client, character, db):
        resp = _post(client, "/chat/send/", {"message": "hi"})
        assert resp.status_code == 400

    def test_unknown_session(self, client, db):
        resp = _post(client, "/chat/send/", {
            "session_id": 9999, "message": "hi",
        })
        assert resp.status_code == 404

    @patch("web.views.check_triggers")
    def test_scenario_injection(self, mock_triggers, client, character, db):
        """Triggered scenarios reach the LLM prompt."""
        mock_triggers.return_value = [{
            "scenario_name": "Village Fire",
            "condition": "fire",
            "action": "React to the fire",
        }]
        mock_retriever = MagicMock()
        mock_retriever.retrieve.return_value = {"documents": [[]], "metadatas": [[]], "ids": [[]]}
        mock_retriever.add_memory = MagicMock()

        session = Session.objects.create(character=character, turn_count=0)
        with patch("web.views.MemoryRetriever") as mock_cls:
            mock_cls.return_value = mock_retriever
            with patch("web.views.LLMClient") as mock_llm_cls:
                mock_llm = MagicMock()
                mock_llm.generate.return_value = "I see fire!"
                mock_llm_cls.return_value = mock_llm
                _post(client, "/chat/send/", {
                    "session_id": session.pk,
                    "message": "Oh no, there is a fire!",
                })
        # The prompt passed to the LLM must contain the scenario action
        prompt_arg = mock_llm.generate.call_args[0][0]
        assert "Village Fire" in prompt_arg
        assert "React to the fire" in prompt_arg

    def test_llm_error_propagated(self, client, character, db):
        """An LLM error string is saved as the response, not raised."""
        mock_retriever = MagicMock()
        mock_retriever.retrieve.return_value = {"documents": [[]], "metadatas": [[]], "ids": [[]]}
        mock_retriever.add_memory = MagicMock()

        session = Session.objects.create(character=character, turn_count=0)
        with patch("web.views.MemoryRetriever") as mock_cls:
            mock_cls.return_value = mock_retriever
            with patch("web.views.LLMClient") as mock_llm_cls:
                mock_llm = MagicMock()
                mock_llm.generate.return_value = "[LLM Error: server down]"
                mock_llm_cls.return_value = mock_llm
                resp = _post(client, "/chat/send/", {
                    "session_id": session.pk,
                    "message": "Hello",
                })
        assert resp.status_code == 200
        assert resp.json()["response"] == "[LLM Error: server down]"


# ---------------------------------------------------------------------------
# Management: sessions & characters
# ---------------------------------------------------------------------------

class TestManagePage:
    def test_renders(self, client, character):
        resp = client.get("/manage/")
        assert resp.status_code == 200

    def test_view_session(self, client, character):
        session = Session.objects.create(character=character, turn_count=0)
        SessionTurn.objects.create(
            session=session, turn_number=1,
            user_message="hi", character_response="hello",
        )
        resp = client.get(f"/manage/session/{session.pk}/")
        assert resp.status_code == 200
        assert "hi" in resp.content.decode()


class TestCharacterData:
    def test_get_character_data(self, client, character, db):
        Trait.objects.create(
            name="brave", weight=8.0, character=character, is_core=True
        )
        resp = _post(client, "/manage/get_char/", {"id": character.pk})
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Rex"
        assert data["personality"]["voice"] == "gruff"
        assert data["traits"] == [
            {"id": character.active_traits.first().pk,
             "name": "brave", "weight": 8.0, "is_core": True}
        ]

    def test_save_character(self, client, character, db):
        resp = _post(client, "/manage/char/save/", {
            "id": character.pk,
            "name": "Rex the Bold",
            "description": "A braver dragon",
            "voice": "gruff",
            "quirks": "hoards coins",
            "backstory": "born in a volcano",
        })
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        character.refresh_from_db()
        assert character.name == "Rex the Bold"
        assert character.personality["backstory"] == "born in a volcano"

    def test_save_trait_new(self, client, character, db):
        resp = _post(client, "/manage/trait/save/", {
            "character_id": character.pk,
            "name": "loyal",
            "weight": "7.5",
            "is_core": True,
        })
        assert resp.status_code == 200
        t = character.active_traits.get(name="loyal")
        assert t.weight == 7.5
        assert t.is_core is True

    def test_save_trait_update(self, client, character, db):
        t = Trait.objects.create(
            name="loyal", weight=5.0, character=character
        )
        resp = _post(client, "/manage/trait/save/", {
            "character_id": character.pk,
            "trait_id": t.pk,
            "name": "loyal",
            "weight": "9.0",
        })
        assert resp.status_code == 200
        t.refresh_from_db()
        assert t.weight == 9.0

    def test_delete_trait(self, client, character, db):
        t = Trait.objects.create(name="old", weight=1.0, character=character)
        resp = _post(client, "/manage/trait/delete/", {"trait_id": t.pk})
        assert resp.status_code == 200
        assert not Trait.objects.filter(pk=t.pk).exists()


# ---------------------------------------------------------------------------
# Management: memories
# ---------------------------------------------------------------------------

class TestMemories:
    def test_get_memories(self, client, character, db):
        Memory.objects.create(
            character=character, memory_type="fact",
            text="Kaya loves fish.", embedding_id="a",
        )
        Memory.objects.create(
            character=character, memory_type="event",
            text="Old event.", embedding_id="b", is_archived=True,
        )
        resp = _post(client, "/manage/get_memories/", {"id": character.pk})
        assert resp.status_code == 200
        data = resp.json()
        texts = [m["text"] for m in data["memories"]]
        assert "Kaya loves fish." in texts
        assert "Old event." not in texts

    @patch("memory.services.memory_engine")
    def test_delete_memory(self, mock_engine, client, character, db):
        m = Memory.objects.create(
            character=character, memory_type="fact",
            text="to delete.", embedding_id="del-1",
        )
        mock_engine.delete = MagicMock()
        resp = _post(client, "/manage/mem/delete/", {"mem_id": m.pk})
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        assert not Memory.objects.filter(pk=m.pk).exists()
        mock_engine.delete.assert_called_once_with("del-1")


# ---------------------------------------------------------------------------
# Management: global settings
# ---------------------------------------------------------------------------

class TestGlobalSettings:
    def test_get_and_save(self, client, db):
        resp = _post(client, "/manage/global/get/", {})
        assert resp.status_code == 200
        assert resp.json()["instructions"] == []

        resp = _post(client, "/manage/global/save/", {
            "instructions": ["Speak German.", "Stay in character."],
        })
        assert resp.status_code == 200
        assert resp.json()["success"] is True

        resp = _post(client, "/manage/global/get/", {})
        assert resp.json()["instructions"] == ["Speak German.", "Stay in character."]


# ---------------------------------------------------------------------------
# Management: worlds & locations
# ---------------------------------------------------------------------------

class TestWorlds:
    def test_save_new_world(self, client, db):
        resp = _post(client, "/manage/world/save/", {
            "name": "Ardania",
            "description": "A fantasy world",
            "rules": "No flying.",
            "lore": [{"name": "History", "content": "Ancient magic."}],
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        w = World.objects.get(name="Ardania")
        assert w.pk == data["world_id"]
        assert w.rules == "No flying."

    def test_update_world(self, client, db):
        w = World.objects.create(
            name="Ardania", description="old", rules="", lore=[]
        )
        resp = _post(client, "/manage/world/save/", {
            "id": w.pk,
            "name": "Ardania",
            "description": "new",
        })
        assert resp.status_code == 200
        w.refresh_from_db()
        assert w.description == "new"

    def test_save_location(self, client, db):
        w = World.objects.create(name="W", description="")
        resp = _post(client, "/manage/location/save/", {
            "world_id": w.pk,
            "name": "Cave",
            "description": "A dark cave.",
        })
        assert resp.status_code == 200
        loc = Location.objects.get(name="Cave")
        assert loc.pk == resp.json()["location_id"]

    def test_delete_location(self, client, db):
        w = World.objects.create(name="W", description="")
        loc = Location.objects.create(world=w, name="Cave", description="")
        resp = _post(client, "/manage/location/delete/", {"location_id": loc.pk})
        assert resp.status_code == 200
        assert not Location.objects.filter(pk=loc.pk).exists()
