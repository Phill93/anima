from django.contrib import admin
from .models import World, Location


class LocationInline(admin.TabularInline):
    model = Location
    extra = 1


@admin.register(World)
class WorldAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at')
    search_fields = ('name', 'description')
    inlines = [LocationInline]