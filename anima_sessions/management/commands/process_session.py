"""
Post-Session Processing.

Usage: python manage.py process_session --session <id> [--condense]

Actions:
1. Generate Session Summary (LLM)
2. Run Trait Evolution (Delta-based)
3. Update Traits in DB
4. Store Summary as Memory
5. Optional: Run Memory Condensation
6. Optional: Update Relationships
"""
import json
from django.core.management.base import BaseCommand, CommandError
from anima_sessions.models import Session, SessionTurn
from characters.models import Character, Trait
from characters.evolution import TraitEvolution
from characters.condensation import MemoryCondensation
from characters.llm import LLMClient
from memory.retriever import MemoryRetriever
from memory.services import MemoryEngine
from memory.models import Memory
from relationships.models import Relationship
from relationships.updater import RelationshipUpdater


class Command(BaseCommand):
    help = "Process a completed RP session (Summary, Evolution, Condensation)"

    def add_arguments(self, parser):
        parser.add_argument("--session", type=int, required=True, help="Session ID")
        parser.add_argument("--condense", action="store_true", help="Run memory condensation")
        parser.add_argument("--llm-url", type=str, default="http://localhost:8001/v1")
        parser.add_argument("--llm-model", type=str, default="local-model")

    def handle(self, *args, **options):
        # --- Setup ---
        try:
            session = Session.objects.get(pk=options["session"])
        except Session.DoesNotExist:
            raise CommandError(f"Session {options['session']} not found")

        character = session.character
        llm = LLMClient(base_url=options["llm_url"], model=options["llm_model"])
        retriever = MemoryRetriever()
        engine = MemoryEngine()

        # --- 1. Generate Summary ---
        self.stdout.write("Generating session summary...")
        turns = list(session.turns.order_by("turn_number").values_list("user_message", "character_response"))
        turns_text = "\n".join([f"User: {u}\nCharacter: {c}" for u, c in turns])
        
        summary_prompt = f"""
Summarize the following RP session between the user and {character.name} in 3-5 sentences.
Focus on events, emotional shifts, and key revelations.

Session Log:
{turns_text[-2000:]}  # Keep last 2000 chars for context window safety

Summary:
"""
        summary = llm.generate(summary_prompt, temperature=0.5, max_tokens=512)
        session.summary = summary
        session.save()
        self.stdout.write(self.style.SUCCESS(f"Summary: {summary[:100]}..."))

        # --- 2. Store Summary as Memory ---
        self.stdout.write("Storing summary as memory...")
        retriever.add_memory(
            character=character,
            text=summary,
            memory_type="event",
            embedding_id=f"session_{session.pk}",
        )

        # --- 3. Trait Evolution ---
        self.stdout.write("Running Trait Evolution...")
        evolution = TraitEvolution(llm)
        changes = evolution.evaluate(character, summary)
        
        for change in changes.get("changed", []):
            trait, created = Trait.objects.get_or_create(
                character=character,
                name=change["trait"]
            )
            if not trait.is_core:
                trait.weight = change["new"]
                trait.evolved_from_session = session
                trait.save()
                self.stdout.write(f"  Updated trait '{trait.name}' -> {trait.weight}")

        for new_trait_data in changes.get("new_traits", []):
            Trait.objects.update_or_create(
                character=character,
                name=new_trait_data["trait"],
                defaults={"weight": new_trait_data["weight"]}
            )
            self.stdout.write(f"  Added trait '{new_trait_data['trait']}'")

        # --- 4. Relationship Updates ---
        self.stdout.write("Updating Relationships...")
        updater = RelationshipUpdater(llm)
        all_chars = list(Character.objects.exclude(pk=character.pk).values_list("name", flat=True))
        
        if all_chars:
            interactions = updater.analyze(character, summary, all_chars)
            for interaction in interactions.get("interactions", []):
                other_char_name = interaction["character"]
                try:
                    other_char = Character.objects.get(name=other_char_name)
                    rel, created = Relationship.objects.get_or_create(
                        character_a=character,
                        character_b=other_char
                    )
                    old_score = rel.score
                    rel.score = max(-1.0, min(1.0, rel.score + interaction["delta"]))
                    rel.notes += f"\n[Session {session.pk}] {interaction['reason']}"
                    rel.save()
                    self.stdout.write(f"  Updated relation with '{other_char_name}': {old_score} -> {rel.score}")
                except Character.DoesNotExist:
                    pass

        # --- 5. Memory Condensation (Optional) ---
        if options["condense"]:
            self.stdout.write("Running Memory Condensation...")
            condenser = MemoryCondensation(llm)
            all_memories = character.memories.filter(is_archived=False).values_list("text", flat=True)
            if len(all_memories) > 10:
                condensed = condenser.condense(character, list(all_memories))
                # This is a simplified approach: add condensed version as a fact
                retriever.add_memory(character, condensed, "fact", f"condensed_{session.pk}")
                self.stdout.write(self.style.SUCCESS("Memories condensed."))

        self.stdout.write(self.style.SUCCESS(f"Session {session.pk} processing complete."))