from django.db import models


class World(models.Model):
    """A fictional world/setting."""
    name = models.CharField(max_length=255)
    description = models.TextField()
    rules = models.TextField(blank=True, default="")
    lore = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'worlds'

    def __str__(self):
        return self.name


class Location(models.Model):
    """A specific point of interest within a world."""
    name = models.CharField(max_length=255)
    world = models.ForeignKey(World, on_delete=models.CASCADE, related_name="locations")
    description = models.TextField()
    connections = models.JSONField(default=list)

    class Meta:
        db_table = 'world_locations'

    def __str__(self):
        return f"{self.name} (in {self.world.name})"
