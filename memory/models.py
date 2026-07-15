from django.db import models


class MemoryType(models.TextChoices):
    FACT = "fact", "Fact"
    EVENT = "event", "Event"
    EMOTION = "emotion", "Emotion"
    RELATIONSHIP = "relationship", "Relationship"
    PREFERENCE = "preference", "Preference"


class Memory(models.Model):
    """
    A single memory entry for a character.

    Stored in both Chroma (for semantic search) and SQLite (for
    archival, dedup tracking, and decay management).
    """
    character = models.ForeignKey(
        'characters.Character', on_delete=models.CASCADE, related_name="memories"
    )
    memory_type = models.CharField(max_length=20, choices=MemoryType.choices)
    text = models.TextField()
    embedding_id = models.CharField(max_length=100, blank=True, default="")
    score = models.FloatField(default=1.0)
    is_archived = models.BooleanField(default=False)
    session_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'memory_entries'
        indexes = [
            models.Index(fields=['character', 'is_archived']),
            models.Index(fields=['memory_type']),
        ]

    def __str__(self):
        return f"[{self.get_memory_type_display()}] {self.text[:50]}"
