"""
Tests for the scenarios app: models and the trigger evaluator.
"""
import pytest
from django.db.utils import IntegrityError

from scenarios.models import Scenario, ScenarioTrigger
from scenarios.evaluator import check_triggers


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class TestModels:
    def test_scenario_str(self, db):
        s = Scenario.objects.create(name="Village Fire", description="A fire burns.")
        assert str(s) == "Village Fire"

    def test_scenario_defaults(self, db):
        s = Scenario.objects.create(name="S", description="d")
        assert s.triggers == ""
        assert s.starting_conditions == ""
        assert s.world is None

    def test_trigger_str(self, db):
        s = Scenario.objects.create(name="Fire", description="d")
        t = ScenarioTrigger.objects.create(
            scenario=s, condition="fire", action="React"
        )
        assert "Fire" in str(t)

    def test_trigger_cascade_delete(self, db):
        """Deleting a scenario removes its triggers."""
        s = Scenario.objects.create(name="Fire", description="d")
        ScenarioTrigger.objects.create(scenario=s, condition="fire", action="React")
        s.delete()
        assert ScenarioTrigger.objects.count() == 0

    def test_trigger_related_name(self, db):
        s = Scenario.objects.create(name="Fire", description="d")
        t = ScenarioTrigger.objects.create(scenario=s, condition="fire", action="React")
        assert s.scenario_triggers.count() == 1
        assert s.scenario_triggers.first().pk == t.pk


# ---------------------------------------------------------------------------
# Evaluator
# ---------------------------------------------------------------------------

class TestCheckTriggers:
    def test_no_scenarios(self, db):
        assert check_triggers("anything") == []

    def test_no_match(self, db):
        s = Scenario.objects.create(name="Fire", description="d")
        ScenarioTrigger.objects.create(scenario=s, condition="fire", action="React")
        assert check_triggers("the weather is nice") == []

    def test_match_returns_dict(self, db):
        s = Scenario.objects.create(
            name="Village Fire",
            description="A fire is burning in the village.",
            starting_conditions="The lights go out.",
        )
        ScenarioTrigger.objects.create(
            scenario=s, condition="fire", action="React to the fire"
        )
        results = check_triggers("Oh no, there is a FIRE!")
        assert len(results) == 1
        r = results[0]
        assert r["scenario_name"] == "Village Fire"
        assert r["scenario_desc"] == "A fire is burning in the village."
        assert r["condition"] == "fire"
        assert r["action"] == "React to the fire"
        assert r["starting_conditions"] == "The lights go out."

    def test_case_insensitive(self, db):
        s = Scenario.objects.create(name="S", description="d")
        ScenarioTrigger.objects.create(scenario=s, condition="fire", action="a")
        assert len(check_triggers("Fire!")) == 1

    def test_multiple_triggers_multiple_scenarios(self, db):
        s1 = Scenario.objects.create(name="S1", description="d1")
        s2 = Scenario.objects.create(name="S2", description="d2")
        ScenarioTrigger.objects.create(scenario=s1, condition="fire", action="a1")
        ScenarioTrigger.objects.create(scenario=s2, condition="water", action="a2")
        results = check_triggers("fire and water")
        assert len(results) == 2
