from django.contrib import admin
from .models import Session, SessionTurn


class TurnInline(admin.TabularInline):
    model = SessionTurn
    extra = 1
    fields = ('turn_number', 'user_message', 'character_response', 'created_at')
    readonly_fields = ('created_at',)


@admin.register(Session)
class SessionAdmin(admin.ModelAdmin):
    list_display = ('character', 'world', 'scenario', 'turn_count', 'created_at')
    list_filter = ('character', 'world')
    search_fields = ('character__name', 'summary')
    inlines = [TurnInline]