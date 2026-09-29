"""
Tests for the relationships app: the Relationship model.
"""
import pytest
from django.db.utils import IntegrityError

from characters.models import Character
from relationships.models import Relationship


@pytest.fixture
def c1(db):
    return Character.objects.create(name="Kaya", description="")


@pytest.fixture
def c2(db):
    return Character.objects.create(name="Bo", description="")


class TestRelationship:
    def test_str(self, db, c1, c2):
        r = Relationship.objects.create(character_a=c1, character_b=c2, score=5.0)
        assert str(r) == "Kaya ↔ Bo"

    def test_defaults(self, db, c1, c2):
        r = Relationship.objects.create(character_a=c1, character_b=c2)
        assert r.score == 0.0
        assert r.notes == ""

    def test_unique_pair(self, db, c1, c2):
        """The same (a, b) pair cannot be created twice."""
        Relationship.objects.create(character_a=c1, character_b=c2)
        with pytest.raises(IntegrityError):
            Relationship.objects.create(character_a=c1, character_b=c2)

    def test_order_matters(self, db, c1, c2):
        """(a, b) and (b, a) are distinct rows (bidirectional storage)."""
        r1 = Relationship.objects.create(character_a=c1, character_b=c2)
        r2 = Relationship.objects.create(character_a=c2, character_b=c1)
        assert r1.pk != r2.pk

    def test_related_names(self, db, c1, c2):
        r = Relationship.objects.create(character_a=c1, character_b=c2)
        assert c1.relationships_as_a.count() == 1
        assert c2.relationships_as_b.count() == 1

    def test_cascade_delete(self, db, c1, c2):
        """Deleting a character removes its relationships."""
        Relationship.objects.create(character_a=c1, character_b=c2)
        c1.delete()
        assert Relationship.objects.count() == 0
