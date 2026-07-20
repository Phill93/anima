from django.db import models


class Character(models.Model):
    """Core character entity."""
    name = models.CharField(max_length=255)
    description = models.TextField()
    personality = models.JSONField(default=dict)  # voice, quirks, kinks, backstory
    traits = models.JSONField(default=dict)       # { "trait_name": 0.5 }
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    world = models.ForeignKey(
        'worlds.World',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='characters',
    )

    class Meta:
        db_table = 'characters'

    def __str__(self):
        return self.name


class Trait(models.Model):
    """Individual trait with weight and evolution tracking."""
    name = models.CharField(max_length=100)
    weight = models.FloatField(default=1.0)
    character = models.ForeignKey(
        Character, related_name="active_traits", on_delete=models.CASCADE
    )
    evolved_from_session = models.ForeignKey(
        'anima_sessions.Session', null=True, on_delete=models.SET_NULL
    )
    is_core = models.BooleanField(
        default=False, help_text="If True, this trait cannot be condensed."
    )

    class Meta:
        db_table = 'traits'
        unique_together = ('character', 'name')

    def __str__(self):
        return f"{self.character.name}: {self.name} ({self.weight})"


class GlobalConfig(models.Model):
    """Global system-wide configurations (e.g., instructions, language settings)."""
    key = models.CharField(max_length=100)
    value = models.TextField()
    order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'global_config'

    def __str__(self):
        return f"{self.key}: {self.value}"
