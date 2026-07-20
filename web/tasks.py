"""
Celery Tasks for Anima RP System.
"""
from celery import shared_task
import os


@shared_task
def run_chat_turn(session_id, user_message):
    """
    Celery task to process a chat turn asynchronously.
    """
    # Imports inside task to avoid circular imports and ensure it works in worker
    from anima_sessions.models import Session, SessionTurn
    from memory.retriever import MemoryRetriever
    from characters.prompt_builder import PromptBuilder
    from characters.llm import LLMClient
    from scenarios.evaluator import check_triggers
    from worlds.models import World

    session = Session.objects.get(pk=session_id)
    character = session.character

    # Setup
    retriever = MemoryRetriever()
    builder = PromptBuilder(max_tokens=4096)

    # LLM Config
    llm_base = os.getenv("LLM_BASE_URL", "https://ki-toolbox.scc.kit.edu/api/v1")
    llm_model = os.getenv("LLM_MODEL", "kit.mistral-small-4-119b-a8b")
    llm_key = os.getenv("KIT_API_KEY", os.getenv("LLM_API_KEY", ""))

    if not llm_key:
        env_path = os.path.expanduser("~/.hermes/.env")
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    if line.startswith("KIT_API_KEY="):
                        llm_key = line.strip().split("=", 1)[1]
                        break

    llm = LLMClient(base_url=llm_base, api_key=llm_key, model=llm_model)

    # Context
    recent_turns = list(session.turns.order_by("-turn_number")[:10])
    conversation = [(t.user_message, t.character_response) for t in recent_turns]

    memory_results = retriever.retrieve(character, user_message, n_results=3)
    active_scenarios = check_triggers(user_message)

    world_context = ""
    world_obj = character.world
    if not world_obj:
        try:
            world_obj = World.objects.first()
        except Exception:
            pass
    if world_obj:
        locs = [f"- {loc.name}: {loc.description}" for loc in world_obj.locations.all()[:3]]
        world_context = f"{world_obj.name}: {world_obj.description}. Locations: {'; '.join(locs)}."

    prompt_result = builder.build(
        character,
        world_context=world_context,
        memories=memory_results,
        conversation=conversation,
        scenario=active_scenarios
    )
    prompt = prompt_result['prompt']
    debug_info = prompt_result['debug']

    response = llm.generate(prompt, temperature=0.8, max_tokens=2048)

    # Save turn
    turn = SessionTurn.objects.create(
        session=session,
        turn_number=session.turn_count + 1,
        user_message=user_message,
        character_response=response,
    )
    session.turn_count += 1
    session.save()

    # Save Memory
    retriever.add_memory(
        character=character,
        text=f"{user_message} -> {response[:100]}",
        memory_type="event",
        embedding_id=f"session_{session.pk}_turn_{turn.pk}"
    )

    return {
        'response': response,
        'turn_number': turn.turn_number,
        'debug': debug_info,
    }


@shared_task
def consolidate_memories():
    """
    Task to consolidate old sessions into long-term memories.
    """
    from characters.llm import LLMClient
    from memory.retriever import MemoryRetriever
    from characters.models import Character
    from anima_sessions.models import Session

    llm_key = os.getenv("KIT_API_KEY", os.getenv("LLM_API_KEY", ""))
    if not llm_key:
        env_path = os.path.expanduser("~/.hermes/.env")
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    if line.startswith("KIT_API_KEY="):
                        llm_key = line.strip().split("=", 1)[1]
                        break

    llm = LLMClient(
        base_url=os.getenv("LLM_BASE_URL", "https://ki-toolbox.scc.kit.edu/api/v1"),
        api_key=llm_key,
        model=os.getenv("LLM_MODEL", "kit.mistral-small-4-119b-a8b")
    )
    retriever = MemoryRetriever()

    processed_count = 0
    # Iterate over all characters
    for char in Character.objects.all():
        # Get sessions older than 3 days with > 5 turns that haven't been summarized
        sessions = Session.objects.filter(
            character=char,
            turn_count__gt=5
        ).exclude(summary__exact="").order_by("-created_at")[:10]

        for s in sessions:
            turns = list(s.turns.order_by("turn_number")[:10])
            # Create a summary prompt
            summary_prompt = f"Summarize this conversation into 3 bullet points:\n"
            for t in turns:
                summary_prompt += f"User: {t.user_message}\nChar: {t.character_response}\n"

            summary = llm.generate(summary_prompt, temperature=0.2, max_tokens=150)
            s.summary = summary
            s.save()

            # Add summary as a memory
            retriever.add_memory(
                character=char,
                text=f"Session Summary: {summary}",
                memory_type="event",
                embedding_id=f"session_summary_{s.pk}"
            )
            processed_count += 1

    return f"Consolidated {processed_count} sessions."