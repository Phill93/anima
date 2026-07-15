"""
Trait Evolution Engine.

- Delta-based evolution (only changed traits).
- Core traits are immutable.
- Uses LLM to analyze session summary and suggest changes.
"""
import json
import re


class TraitEvolution:
    def __init__(self, llm_client):
        self.llm = llm_client

    def evaluate(self, character, session_summary: str) -> dict:
        """
        Analyze the session summary and suggest trait changes.

        Returns:
        {
            "changed": [ {"trait": "...", "old": 0.5, "new": 0.7, "reason": "..."} ],
            "new_traits": [ {"trait": "...", "weight": 0.5, "reason": "..."} ]
        }
        """
        # Get current traits
        traits = list(character.active_traits.filter(is_core=False).values("name", "weight"))
        trait_str = json.dumps(traits, indent=2)

        prompt = f"""
You are an AI analyzing a character's personality growth.

Current Traits:
{trait_str}

Session Summary:
{session_summary}

Based on the session, which traits have changed? Do not suggest changes for traits that remain stable.

Respond ONLY with a JSON object:
{{
  "changed": [
    {{"trait": "name", "old": 0.5, "new": 0.7, "reason": "..."}}
  ],
  "new_traits": [
    {{"trait": "name", "weight": 0.5, "reason": "..."}}
  ]
}}
"""
        response = self.llm.generate(prompt, temperature=0.2, max_tokens=512)
        return self._parse_json(response)

    def _parse_json(self, text: str) -> dict:
        """Extract JSON from LLM response."""
        match = re.search(r'\{(.*)\}', text, re.DOTALL)
        if match:
            try:
                return json.loads("{" + match.group(1) + "}")
            except json.JSONDecodeError:
                pass
        return {"changed": [], "new_traits": []}
