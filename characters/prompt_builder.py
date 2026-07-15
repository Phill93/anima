"""
Prompt Builder - Assembles the final prompt for the LLM.

Strategy:
- Core Traits (pinned)
- Top 5 Active Traits (by weight)
- Top 3 Memories (semantic retrieval)
- World Snippet (max 200 tokens)
- Last N Turns (dynamic, fills remaining budget)
"""
import re
from .models import Character, Trait


def count_tokens(text: str) -> int:
    """Rough token estimation (1 token ~= 4 chars for LLMs)."""
    return max(1, len(text) // 4)


class PromptBuilder:
    def __init__(self, max_tokens: int = 4096):
        self.max_tokens = max_tokens

    def build(self, character: Character, world_context: str = "", memories: list = None, conversation: list = None) -> str:
        """
        Build the complete prompt for the LLM.
        
        Args:
            character: The Character instance
            world_context: Pre-rendered world info snippet
            memories: List of memory dicts from Chroma query
            conversation: List of (user, character) turn dicts
        """
        parts = []

        # --- System Header ---
        parts.append(f"You are {character.name}.")

        # --- Core Traits (pinned, immutable) ---
        core_traits = character.active_traits.filter(is_core=True)
        if core_traits.exists():
            core_text = ", ".join([
                f"{t.name} ({t.weight})" for t in core_traits
            ])
            parts.append(f"Core Traits (fixed): {core_text}")

        # --- Active Traits (Top 5 by weight) ---
        active_traits = character.active_traits.filter(is_core=False).order_by("-weight")[:5]
        if active_traits.exists():
            traits_text = ", ".join([
                f"{t.name} ({t.weight})" for t in active_traits
            ])
            parts.append(f"Current Traits: {traits_text}")

        # --- Personality / Voice ---
        personality = character.personality or {}
        if personality:
            voice_parts = []
            for key in ["voice", "quirks", "backstory"]:
                if key in personality:
                    voice_parts.append(f"{key}: {personality[key]}")
            if voice_parts:
                parts.append("Personality: " + " | ".join(voice_parts))

        # --- Memories (Top 3) ---
        if memories:
            memory_texts = []
            for m in (memories.get("documents", [[]])[0] if isinstance(memories, dict) else []):
                memory_texts.append(m)
            if memory_texts:
                parts.append("Relevant Memories: " + "; ".join(memory_texts[:3]))

        # --- World Context ---
        if world_context:
            parts.append(f"World: {world_context}")

        # --- Conversation History ---
        if conversation:
            # Build from last N turns, respect token budget
            convo_parts = []
            total_tokens = sum(count_tokens(p) for p in parts)
            for user_msg, char_resp in reversed(conversation[-10:]):
                turn = f"User: {user_msg}\nYou: {char_resp}"
                if total_tokens + count_tokens(turn) < self.max_tokens:
                    convo_parts.append(turn)
                    total_tokens += count_tokens(turn)

            if convo_parts:
                parts.append("Recent Conversation:\n" + "\n\n".join(reversed(convo_parts)))

        return "\n\n".join(parts)
