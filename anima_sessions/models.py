from django.db import models


class Session(models.Model):
    """A single RP session."""
    character = models.ForeignKey(
        'characters.Character', on_delete=models.CASCADE, related_name="sessions"
    )
    world = models.ForeignKey(
        'worlds.World', on_delete=models.SET_NULL, null=True, blank=True
    )
    scenario = models.ForeignKey(
        'scenarios.Scenario', on_delete=models.SET_NULL, null=True, blank=True
    )
    summary = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    turn_count = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = 'sessions'

    def __str__(self):
        return f"Session #{self.id} — {self.character.name} ({self.turn_count} turns)"


class SessionTurn(models.Model):
    """A single turn within a session."""
    session = models.ForeignKey(
        Session, related_name="turns", on_delete=models.CASCADE
    )
    turn_number = models.PositiveIntegerField()
    user_message = models.TextField()
    character_response = models.TextField()
    embedding_id = models.CharField(max_length=100, blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'session_turns'
        ordering = ['turn_number']
        unique_together = ('session', 'turn_number')

    def __str__(self):
        return f"Turn {self.turn_number} — {self.session.character.name}"
