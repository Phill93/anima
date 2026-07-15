"""
Memory Condensation.

- Summarizes multiple memories into a single, dense memory.
- Runs periodically (e.g., every 10 sessions).
"""
import json
from .evolution import TraitEvolution


class MemoryCondensation:
    def __init__(self, llm_client):
        self.llm = llm_client

    def condense(self, character, memories: list) -> str:
        """
        Take a list of memory texts and return a condensed summary.
        """
        memory_text = "\n".join([f"- {m}" for m in memories[:10]])
        
        prompt = f"""
Condense the following memories about the character {character.name} into a single, dense paragraph.
Keep the key facts and emotional resonance. Remove redundancy.

Memories:
{memory_text}

Condensed Memory:
"""
        response = self.llm.generate(prompt, temperature=0.3, max_tokens=256)
        return response.strip()
