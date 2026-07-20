from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
import os
import json

from characters.models import Character, Trait, GlobalConfig
from characters.global_config import get_global_instructions, set_global_instructions
from anima_sessions.models import Session, SessionTurn
from memory.retriever import MemoryRetriever
from characters.prompt_builder import PromptBuilder
from characters.llm import LLMClient
from scenarios.evaluator import check_triggers
from worlds.models import World, Location


def index(request):
    """List all characters with their recent sessions."""
    characters = Character.objects.prefetch_related('active_traits').all()
    char_ids = [c.pk for c in characters]
    recent_sessions = Session.objects.filter(character_id__in=char_ids).order_by('character_id', '-created_at')

    # Build a mapping of character -> last session
    session_map = {}
    for s in recent_sessions:
        if s.character_id not in session_map:
            session_map[s.character_id] = s

    # Combine characters and sessions for easier template access
    char_list = []
    for c in characters:
        char_list.append({
            'character': c,
            'last_session': session_map.get(c.pk)
        })

    return render(request, 'web/index.html', {'char_list': char_list})


@csrf_exempt
@require_POST
def chat_init(request):
    """Start a new session."""
    data = json.loads(request.body)
    character_id = data.get('character_id')

    if not character_id:
        return JsonResponse({'error': 'No character_id provided'}, status=400)

    character = get_object_or_404(Character, pk=character_id)

    session = Session.objects.create(
        character=character,
        turn_count=0,
    )

    return JsonResponse({
        'session_id': session.pk,
        'character_name': character.name,
    })


@csrf_exempt
@require_POST
def chat_send(request):
    """Process a turn: input -> prompt -> LLM -> response + memory."""
    data = json.loads(request.body)
    session_id = data.get('session_id')
    user_message = data.get('message', '').strip()

    if not session_id or not user_message:
        return JsonResponse({'error': 'Missing session_id or message'}, status=400)

    session = get_object_or_404(Session, pk=session_id)
    character = session.character

    # --- Setup ---
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

    # --- Build Context ---
    recent_turns = list(session.turns.order_by("-turn_number")[:10])
    conversation = [(t.user_message, t.character_response) for t in recent_turns]

    # Retrieve memories
    memory_results = retriever.retrieve(character, user_message, n_results=3)

    # Check for active scenario triggers
    active_scenarios = check_triggers(user_message)

    # Retrieve World Context (Fix: pass world_context to builder)
    world_context = ""
    try:
        world_obj = World.objects.first()
        if world_obj:
            locs = [f"- {loc.name}: {loc.description}" for loc in world_obj.locations.all()[:3]]
            world_context = f"{world_obj.name}: {world_obj.description}. Locations: {'; '.join(locs)}."
    except Exception:
        pass

    # Build prompt
    prompt_result = builder.build(character, world_context=world_context, memories=memory_results, conversation=conversation, scenario=active_scenarios)
    prompt = prompt_result['prompt']
    debug_info = prompt_result['debug']

    # Call LLM
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

    # Save as Memory
    retriever.add_memory(
        character=character,
        text=f"{user_message} -> {response[:100]}",
        memory_type="event",
        embedding_id=f"session_{session.pk}_turn_{turn.pk}"
    )

    return JsonResponse({
        'response': response,
        'turn_number': turn.turn_number,
        'debug': debug_info,
    })


def chat(request):
    """Chat view (initial load)."""
    return render(request, 'web/chat.html')


def manage(request):
    """Management dashboard."""
    characters = Character.objects.prefetch_related('active_traits').all()
    sessions = Session.objects.select_related('character').order_by('-created_at')[:20]
    worlds = World.objects.prefetch_related('locations').all()
    return render(request, 'web/manage.html', {'characters': characters, 'sessions': sessions, 'worlds': worlds})


def view_session(request, session_id):
    """View a specific session log."""
    session = get_object_or_404(Session, pk=session_id)
    turns = session.turns.order_by('turn_number')
    return render(request, 'web/session.html', {'session': session, 'turns': turns})


@csrf_exempt
@require_POST
def get_character_data(request):
    """Get character data including traits for the editor."""
    data = json.loads(request.body)
    char = get_object_or_404(Character, pk=data.get('id'))

    traits = [
        {'id': t.pk, 'name': t.name, 'weight': t.weight, 'is_core': t.is_core}
        for t in char.active_traits.all()
    ]

    return JsonResponse({
        'name': char.name,
        'description': char.description,
        'personality': char.personality or {},
        'traits': traits,
    })


@csrf_exempt
@require_POST
def get_character_memories(request):
    """Get all memories for a character from the DB."""
    data = json.loads(request.body)
    char = get_object_or_404(Character, pk=data.get('id'))

    memories = char.memories.filter(is_archived=False).order_by('-created_at')
    mem_list = [
        {
            'id': m.pk,
            'embedding_id': m.embedding_id,
            'text': m.text,
            'type': m.memory_type,
            'created': m.created_at.isoformat(),
        }
        for m in memories[:50]
    ]

    return JsonResponse({'memories': mem_list})


@csrf_exempt
@require_POST
def get_global_settings(request):
    """Get global system instructions."""
    instructions = get_global_instructions()
    return JsonResponse({'instructions': instructions})


@csrf_exempt
@require_POST
def save_global_settings(request):
    """Save global system instructions."""
    data = json.loads(request.body)
    instructions = data.get('instructions', [])
    set_global_instructions(instructions)
    return JsonResponse({'success': True})


@csrf_exempt
@require_POST
def delete_memory(request):
    """Delete a memory."""
    data = json.loads(request.body)
    mem_id = data.get('mem_id')

    mem = get_object_or_404(__import__('memory.models', fromlist=['Memory']).Memory, pk=mem_id)
    # Also delete from Chroma (use the shared singleton instance)
    from memory.services import memory_engine
    memory_engine.delete(mem.embedding_id)
    mem.delete()

    return JsonResponse({'success': True})


@csrf_exempt
@require_POST
def save_character(request):
    """Save character details."""
    data = json.loads(request.body)
    character_id = data.get('id')
    char = get_object_or_404(Character, pk=character_id)

    char.name = data.get('name', char.name)
    char.description = data.get('description', char.description)
    # Personality is stored as a JSON field
    char.personality = {
        "voice": data.get('voice', ''),
        "quirks": data.get('quirks', ''),
        "backstory": data.get('backstory', ''),
    }
    char.save()

    return JsonResponse({'success': True})


@csrf_exempt
@require_POST
def save_trait(request):
    """Add or update a trait."""
    data = json.loads(request.body)
    character_id = data.get('character_id')
    trait_id = data.get('trait_id')

    defaults = {
        'name': data.get('name', ''),
        'weight': float(data.get('weight', 0.5)),
        'is_core': bool(data.get('is_core', False)),
    }

    if trait_id:
        trait = get_object_or_404(Trait, pk=trait_id)
        if defaults['name']: trait.name = defaults['name']
        trait.weight = defaults['weight']
        trait.is_core = defaults['is_core']
        trait.save()
    else:
        Trait.objects.create(
            character_id=character_id,
            **defaults
        )

    return JsonResponse({'success': True})


@csrf_exempt
@require_POST
def delete_trait(request):
    """Delete a trait."""
    data = json.loads(request.body)
    trait_id = data.get('trait_id')
    trait = get_object_or_404(Trait, pk=trait_id)
    trait.delete()
    return JsonResponse({'success': True})


@csrf_exempt
@require_POST
def save_world(request):
    """Create or update a world."""
    data = json.loads(request.body)
    world_id = data.get('id')

    if world_id:
        world = get_object_or_404(World, pk=world_id)
    else:
        world = World()

    world.name = data.get('name', world.name)
    world.description = data.get('description', world.description)
    world.rules = data.get('rules', world.rules)
    world.lore = data.get('lore', world.lore)
    world.save()

    return JsonResponse({'success': True, 'world_id': world.pk})


@csrf_exempt
@require_POST
def save_location(request):
    """Create or update a location."""
    data = json.loads(request.body)
    location_id = data.get('id')

    if location_id:
        location = get_object_or_404(Location, pk=location_id)
    else:
        location = Location()

    location.name = data.get('name', location.name)
    location.description = data.get('description', location.description)
    location.connections = data.get('connections', location.connections)
    location.world_id = data.get('world_id')
    location.save()

    return JsonResponse({'success': True, 'location_id': location.pk})


@csrf_exempt
@require_POST
def delete_location(request):
    """Delete a location."""
    data = json.loads(request.body)
    location_id = data.get('location_id')
    location = get_object_or_404(Location, pk=location_id)
    location.delete()
    return JsonResponse({'success': True})