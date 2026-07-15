from django.db import models


class Relationship(models.Model):
    """Bidirectional relationship between two characters."""
    character_a = models.ForeignKey(
        'characters.Character', on_delete=models.CASCADE, related_name="relationships_as_a"
    )
    character_b = models.ForeignKey(
        'characters.Character', on_delete=models.CASCADE, related_name="relationships_as_b"
    )
    score = models.FloatField(default=0.0)
    notes = models.TextField(blank=True, default="")
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'relationships'
        unique_together = ('character_a', 'character_b')

    def __str__(self):
        return f"{self.character_a.name} ↔ {self.character_b.name}"