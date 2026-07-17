from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.views.decorators.csrf import csrf_exempt
import os
import json

from characters.models import Character
from anima_sessions.models import Session, SessionTurn
from memory.retriever import MemoryRetriever
from characters.prompt_builder import PromptBuilder
from characters.llm import LLMClient


def index(request):
    """List all characters."""
    characters = Character.objects.all()
    return render(request, 'web/index.html', {'characters': characters})


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
    
    # Build prompt
    prompt = builder.build(character, memories=memory_results, conversation=conversation)
    
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
    })


def chat(request):
    """Chat view (initial load)."""
    return render(request, 'web/chat.html')