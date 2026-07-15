from django.contrib import admin
from .models import Memory


@admin.register(Memory)
class MemoryAdmin(admin.ModelAdmin):
    list_display = ('character', 'memory_type', 'text', 'score', 'is_archived', 'created_at')
    list_filter = ('memory_type', 'is_archived')
    search_fields = ('text', 'character__name')
    readonly_fields = ('embedding_id', 'created_at', 'updated_at')
