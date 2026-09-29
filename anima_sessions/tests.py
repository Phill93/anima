"""
Tests for the anima_sessions app: Session and SessionTurn.
"""
import pytest
from django.db.utils import IntegrityError

from characters.models import Character
from anima_sessions.models import Session, SessionTurn


@pytest.fixture
def character(db):
    return Character.objects.create(name="Kaya", description="")


class TestSession:
    def test_str(self, db, character):
        s = Session.objects.create(character=character, turn_count=3)
        assert "Kaya" in str(s)
        assert "3 turns" in str(s)

    def test_defaults(self, db, character):
        s = Session.objects.create(character=character)
        assert s.turn_count == 0
        assert s.summary == ""
        assert s.world is None
        assert s.scenario is None

    def test_cascade_delete(self, db, character):
        """Deleting a character removes its sessions and turns."""
        s = Session.objects.create(character=character, turn_count=1)
        SessionTurn.objects.create(
            session=s, turn_number=1,
            user_message="hi", character_response="hello",
        )
        character.delete()
        assert Session.objects.count() == 0
        assert SessionTurn.objects.count() == 0


class TestSessionTurn:
    def test_str(self, db, character):
        s = Session.objects.create(character=character)
        t = SessionTurn.objects.create(
            session=s, turn_number=1,
            user_message="hi", character_response="hello",
        )
        assert "Kaya" in str(t)
        assert "Turn 1" in str(t)

    def test_unique_turn_number(self, db, character):
        """The same turn number cannot be saved twice for one session."""
        s = Session.objects.create(character=character)
        SessionTurn.objects.create(
            session=s, turn_number=1,
            user_message="a", character_response="b",
        )
        with pytest.raises(IntegrityError):
            SessionTurn.objects.create(
                session=s, turn_number=1,
                user_message="c", character_response="d",
            )

    def test_turns_ordered_by_number(self, db, character):
        s = Session.objects.create(character=character)
        SessionTurn.objects.create(
            session=s, turn_number=2,
            user_message="second", character_response="2",
        )
        SessionTurn.objects.create(
            session=s, turn_number=1,
            user_message="first", character_response="1",
        )
        turns = list(s.turns.all())
        assert [t.turn_number for t in turns] == [1, 2]

    def test_embedding_id_default(self, db, character):
        s = Session.objects.create(character=character)
        t = SessionTurn.objects.create(
            session=s, turn_number=1,
            user_message="a", character_response="b",
        )
        assert t.embedding_id == ""
