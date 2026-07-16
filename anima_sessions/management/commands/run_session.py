"""
Management command to run an interactive RP session.

Usage: python manage.py run_session --character <id> [--world <id>] [--scenario <id>]
"""
from django.core.management.base import BaseCommand, CommandError
from characters.models import Character, Trait
from worlds.models import World
from scenarios.models import Scenario
from memory.models import Memory
from memory.retriever import MemoryRetriever
from characters.prompt_builder import PromptBuilder
from characters.llm import LLMClient, HybridLLMClient
from anima_sessions.models import Session, SessionTurn


class Command(BaseCommand):
    help = "Run an interactive RP session"

    def add_arguments(self, parser):
        parser.add_argument("--character", type=int, required=True, help="Character ID")
        parser.add_argument("--world", type=int, help="World ID (optional)")
        parser.add_argument("--scenario", type=int, help="Scenario ID (optional)")
        parser.add_argument("--llm-url", type=str, default="http://localhost:8001/v1", help="LLM API base URL")
        parser.add_argument("--llm-model", type=str, default="local-model", help="LLM Model name")

    def handle(self, *args, **options):
        # --- Setup ---
        try:
            character = Character.objects.get(pk=options["character"])
        except Character.DoesNotExist:
            raise CommandError(f"Character with ID {options['character']} not found")

        world = None
        if options["world"]:
            try:
                world = World.objects.get(pk=options["world"])
            except World.DoesNotExist:
                self.stdout.write(self.style.WARNING(f"World {options['world']} not found, continuing without it."))

        scenario = None
        if options["scenario"]:
            try:
                scenario = Scenario.objects.get(pk=options["scenario"])
            except Scenario.DoesNotExist:
                self.stdout.write(self.style.WARNING(f"Scenario {options['scenario']} not found, continuing without it."))

        # Create Session
        session = Session.objects.create(
            character=character,
            world=world,
            scenario=scenario,
            turn_count=0,
        )

        # Initialize components
        retriever = MemoryRetriever()
        builder = PromptBuilder(max_tokens=4096)
        llm = LLMClient(
            base_url=options["llm_url"],
            model=options["llm_model"],
        )

        self.stdout.write(self.style.SUCCESS(f"Starting session with {character.name}..."))
        self.stdout.write("Type 'exit' or 'quit' to end the session. Type 'help' for commands.\n")

        # --- Main Loop ---
        while True:
            try:
                user_input = input("\n> ").strip()
            except (EOFError, KeyboardInterrupt):
                self.stdout.write("\nSession ended.")
                break

            if not user_input:
                continue

            if user_input.lower() in ("exit", "quit", "q"):
                self.stdout.write("Ending session...")
                break

            if user_input.lower() == "help":
                self.stdout.write("Commands: exit, quit, help")
                continue

            # Build context
            world_context = ""
            if world:
                world_context = world.description[:200]

            # Get conversation history (last 10 turns)
            recent_turns = list(session.turns.order_by("-turn_number")[:10])
            conversation = [(t.user_message, t.character_response) for t in recent_turns]

            # Retrieve memories
            memory_results = retriever.retrieve(character, user_input, n_results=3)

            # Build prompt
            prompt = builder.build(character, world_context=world_context, memories=memory_results, conversation=conversation)

            # Call LLM
            response = llm.generate(prompt, temperature=0.8, max_tokens=2048)

            # Save turn
            turn = SessionTurn.objects.create(
                session=session,
                turn_number=session.turn_count + 1,
                user_message=user_input,
                character_response=response,
            )
            session.turn_count += 1
            session.save()

            # Save as Memory (semantic storage)
            memory_text = f"{user_input} -> {response[:100]}"
            retriever.add_memory(
                character=character,
                text=memory_text,
                memory_type="event",
                embedding_id=f"session_{session.pk}_turn_{turn.pk}"
            )

            self.stdout.write(f"\n{response}")

        self.stdout.write(self.style.SUCCESS("Session ended. Goodbye!"))