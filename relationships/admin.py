from django.contrib import admin
from .models import Relationship


@admin.register(Relationship)
class RelationshipAdmin(admin.ModelAdmin):
    list_display = ('character_a', 'character_b', 'score', 'last_updated')
    search_fields = ('character_a__name', 'character_b__name')
    list_filter = ('score',)
    readonly_fields = ('last_updated',)