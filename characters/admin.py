from django.contrib import admin
from .models import Character, Trait


class TraitInline(admin.TabularInline):
    model = Trait
    extra = 1


@admin.register(Character)
class CharacterAdmin(admin.ModelAdmin):
    list_display = ('name', 'created_at', 'updated_at')
    search_fields = ('name', 'description')
    inlines = [TraitInline]


admin.site.register(Trait)