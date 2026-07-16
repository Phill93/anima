"""
Seed command: populates the database with example data.

Usage: python manage.py seed
"""
from django.core.management.base import BaseCommand
from characters.models import Character, Trait
from worlds.models import World, Location
from scenarios.models import Scenario, ScenarioTrigger
from relationships.models import Relationship


class Command(BaseCommand):
    help = "Populate the database with example data"

    def handle(self, *args, **options):
        # --- 1. World ---
        world, created = World.objects.get_or_create(
            name="The Whispering Tavern",
            defaults={
                "description": "A cozy fantasy tavern on the edge of the Darkwood. Rumor has it the barkeep is an ancient wizard, and the cats here can speak.",
                "rules": "Respect the cats. No magic indoors unless asked.",
                "lore": [{"key": "Darkwood", "content": "A forest where time moves differently."}]
            }
        )
        self.stdout.write(self.style.SUCCESS(f"World: {world.name} ({'created' if created else 'exists'})"))

        # --- 2. Location ---
        location, created = Location.objects.get_or_create(
            world=world,
            name="The Cat Corner",
            defaults={
                "description": "A warm nook near the fireplace where three talking cats hold court.",
                "connections": ["Bar", "Kitchen"]
            }
        )
        self.stdout.write(self.style.SUCCESS(f"Location: {location.name}"))

        # --- 3. Character (Nyxa) ---
        nyxa, created = Character.objects.get_or_create(
            name="Nyxa",
            defaults={
                "description": "A young woman with a fierce temper and a hidden soft heart. She travels to find her lost brother.",
                "personality": {
                    "voice": "Direct, slightly gruff, but warm when she trusts someone.",
                    "quirks": "Taps her fingers when thinking. Hugs cats when stressed.",
                    "backstory": "Orphaned young, raised by a traveling merchant guild."
                }
            }
        )
        self.stdout.write(self.style.SUCCESS(f"Character: {nyxa.name} ({'created' if created else 'exists'})"))

        # --- 4. Traits ---
        core_traits = [
            ("Resilient", 0.8, True),
            ("Loyal", 0.9, True),
            ("Guarded", 0.7, True),
        ]

        active_traits = [
            ("Curious", 0.6, False),
            ("Impulsive", 0.5, False),
            ("Cats-loving", 0.8, False),
            ("Cautious around magic", 0.4, False),
        ]

        all_traits = core_traits + active_traits
        for name, weight, is_core in all_traits:
            trait, created = Trait.objects.update_or_create(
                character=nyxa,
                name=name,
                defaults={"weight": weight, "is_core": is_core}
            )
            self.stdout.write(f"  Trait: {name} (weight: {trait.weight}, core: {trait.is_core})")

        # --- 5. Scenario ---
        scenario, created = Scenario.objects.get_or_create(
            world=world,
            name="Arrival at the Tavern",
            defaults={
                "description": "Nyxa enters the tavern for the first time. The atmosphere is warm, but suspicious eyes watch her from the shadows.",
                "triggers": "Nyxa enters",
                "starting_conditions": "Nyxa is tired and hungry. She has 5 gold coins."
            }
        )
        self.stdout.write(self.style.SUCCESS(f"Scenario: {scenario.name}"))

        # --- 6. Scenario Trigger ---
        trigger, created = ScenarioTrigger.objects.get_or_create(
            scenario=scenario,
            condition="Nyxa mentions magic",
            defaults={
                "action": "NPC 'Eldrin' approaches Nyxa asking about her knowledge of spells."
            }
        )

        self.stdout.write(self.style.SUCCESS("🌱 Database seeded successfully!"))
        self.stdout.write("You can now start a session with:")
        self.stdout.write("python manage.py run_session --character 1 --world 1 --scenario 1")