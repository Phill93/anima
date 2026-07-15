"""
Relationship Updater.

Analyzes session turns to detect interactions between characters
and updates relationship scores accordingly.
"""
import json
import re


class RelationshipUpdater:
    def __init__(self, llm_client):
        self.llm = llm_client

    def analyze(self, character, session_summary: str, other_characters: list) -> dict:
        """
        Analyze the session summary for interactions with other characters.

        Args:
            character: The main character
            session_summary: Text summary of the session
            other_characters: List of character names that might have appeared

        Returns:
        {
            "interactions": [
                {"character": "Name", "delta": +0.5, "reason": "..."}
            ]
        }
        """
        char_names = ", ".join(other_characters)
        
        prompt = f"""
Analyze the following session summary for interactions with other characters.
Main character: {character.name}
Other characters present: {char_names}

Session Summary:
{session_summary}

For each interaction, determine:
- The character name
- The relationship change (delta: -1.0 to +1.0)
- The reason

Respond ONLY with a JSON object:
{{
  "interactions": [
    {{"character": "Name", "delta": 0.5, "reason": "..."}}
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
        return {"interactions": []}
