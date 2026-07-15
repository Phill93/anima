from django.db import models


class Scenario(models.Model):
    """A starting situation or scenario template."""
    name = models.CharField(max_length=255)
    world = models.ForeignKey('worlds.World', on_delete=models.SET_NULL, null=True, blank=True)
    description = models.TextField()
    triggers = models.TextField(blank=True, default="")
    starting_conditions = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'scenarios'

    def __str__(self):
        return self.name


class ScenarioTrigger(models.Model):
    """Conditions that trigger a scenario change."""
    scenario = models.ForeignKey(Scenario, on_delete=models.CASCADE, related_name="scenario_triggers")
    condition = models.TextField()
    action = models.TextField()

    class Meta:
        db_table = 'scenario_triggers'

    def __str__(self):
        return f"Trigger for {self.scenario.name}"