"""
Global configuration for the RP system.

Stores settings that apply to ALL characters (e.g., language, RP rules).
"""
from .models import GlobalConfig


def get_global_instructions() -> list:
    """
    Retrieve all global instructions from the database.
    """
    configs = GlobalConfig.objects.filter(is_active=True).order_by('order')
    return [c.value for c in configs]


def set_global_instructions(items: list):
    """
    Save a list of global instructions.
    items: ['Speak German', 'Stay in character', ...]
    """
    GlobalConfig.objects.all().delete()
    for i, text in enumerate(items):
        if text.strip():
            GlobalConfig.objects.create(
                key='instruction',
                value=text.strip(),
                order=i,
                is_active=True,
            )
