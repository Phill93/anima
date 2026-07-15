from django.contrib import admin
from .models import Scenario, ScenarioTrigger


class TriggerInline(admin.TabularInline):
    model = ScenarioTrigger
    extra = 1


@admin.register(Scenario)
class ScenarioAdmin(admin.ModelAdmin):
    list_display = ('name', 'world', 'created_at')
    search_fields = ('name', 'description')
    inlines = [TriggerInline]