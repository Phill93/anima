"""
Tests for the worlds app: World and Location.
"""
import pytest
from worlds.models import World, Location


class TestWorld:
    def test_str(self, db):
        w = World.objects.create(name="Ardania", description="A fantasy world")
        assert str(w) == "Ardania"

    def test_defaults(self, db):
        w = World.objects.create(name="W", description="d")
        assert w.rules == ""
        assert w.lore == []

    def test_lore_json(self, db):
        w = World.objects.create(
            name="W", description="d",
            lore=[{"name": "History", "content": "Ancient magic."}],
        )
        w.refresh_from_db()
        assert w.lore[0]["name"] == "History"

    def test_characters_related_name(self, db):
        from characters.models import Character
        w = World.objects.create(name="Ardania", description="")
        c = Character.objects.create(name="Kaya", description="", world=w)
        assert w.characters.count() == 1
        assert c.world_id == w.pk


class TestLocation:
    def test_str(self, db):
        w = World.objects.create(name="Ardania", description="")
        l = Location.objects.create(name="Dorf", description="A village", world=w)
        assert str(l) == "Dorf (in Ardania)"

    def test_connections_default(self, db):
        w = World.objects.create(name="W", description="")
        l = Location.objects.create(name="L", description="", world=w)
        assert l.connections == []

    def test_locations_related_name(self, db):
        w = World.objects.create(name="Ardania", description="")
        Location.objects.create(name="Dorf", description="", world=w)
        Location.objects.create(name="Wald", description="", world=w)
        assert w.locations.count() == 2

    def test_cascade_delete(self, db):
        """Deleting a world removes its locations."""
        w = World.objects.create(name="W", description="")
        Location.objects.create(name="L", description="", world=w)
        w.delete()
        assert Location.objects.count() == 0
