"""
Tests for the characters app: models, PromptBuilder, LLMClient,
global config service functions.

LLM calls are mocked via urllib.request (no network access needed).
"""
import json
import os
import pytest
from unittest.mock import MagicMock, patch

from characters.llm import LLMClient, HybridLLMClient
from characters.models import Character, GlobalConfig, Trait
from characters.prompt_builder import PromptBuilder, count_tokens
from characters import global_config as gc_service


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class TestModels:
    def test_character_str(self, db):
        c = Character.objects.create(name="Kaya", description="Wolfin")
        assert str(c) == "Kaya"

    def test_trait_str(self, db):
        c = Character.objects.create(name="Kaya", description="")
        t = Trait.objects.create(name="tapfer", weight=8.0, character=c)
        assert str(t) == "Kaya: tapfer (8.0)"

    def test_trait_unique_per_character(self, db):
        """A character cannot have two traits with the same name."""
        c = Character.objects.create(name="Kaya", description="")
        Trait.objects.create(name="tapfer", weight=8.0, character=c)
        from django.db.utils import IntegrityError
        with pytest.raises(IntegrityError):
            Trait.objects.create(name="tapfer", weight=5.0, character=c)

    def test_global_config_defaults(self, db):
        g = GlobalConfig.objects.create(key="rp_rules")
        assert g.value == ""
        assert g.order == 0
        assert g.is_active is True

    def test_character_default_personality(self, db):
        c = Character.objects.create(name="Kaya", description="")
        assert c.personality == {}
        assert c.traits == {}

    def test_trait_core_default(self, db):
        c = Character.objects.create(name="Kaya", description="")
        t = Trait.objects.create(name="tapfer", weight=8.0, character=c)
        assert t.is_core is False

    def test_world_str(self, db):
        from worlds.models import World
        w = World.objects.create(name="Ardania", description="Fantasy world")
        assert str(w) == "Ardania"

    def test_location_str(self, db):
        from worlds.models import World, Location
        w = World.objects.create(name="Ardania", description="")
        l = Location.objects.create(name="Dorf", description="", world=w)
        assert str(l) == "Dorf (in Ardania)"


# ---------------------------------------------------------------------------
# Global config service
# ---------------------------------------------------------------------------

class TestGlobalConfigService:
    def test_set_and_get_instructions(self, db):
        gc_service.set_global_instructions(["Be in character.", "No meta talk."])
        assert gc_service.get_global_instructions() == [
            "Be in character.",
            "No meta talk.",
        ]

    def test_get_empty_when_missing(self, db):
        assert gc_service.get_global_instructions() == []

    def test_set_ignores_blank_entries(self, db):
        gc_service.set_global_instructions(["  ", "Real rule", ""])
        assert gc_service.get_global_instructions() == ["Real rule"]

    def test_set_replaces_old_instructions(self, db):
        gc_service.set_global_instructions(["Old rule."])
        gc_service.set_global_instructions(["New rule."])
        assert gc_service.get_global_instructions() == ["New rule."]


# ---------------------------------------------------------------------------
# Token counting
# ---------------------------------------------------------------------------

class TestCountTokens:
    def test_estimates_by_four_chars(self):
        assert count_tokens("a" * 40) == 10

    def test_minimum_one(self):
        assert count_tokens("") == 1


# ---------------------------------------------------------------------------
# PromptBuilder
# ---------------------------------------------------------------------------

class TestPromptBuilder:
    def test_returns_prompt_and_debug(self, db):
        """build() returns {'prompt': str, 'debug': dict}."""
        c = Character.objects.create(
            name="Kaya", description="A young wolf",
            personality={"voice": "friendly"},
        )
        Trait.objects.create(name="brave", weight=9.0, character=c, is_core=True)
        result = PromptBuilder(character=c) if False else PromptBuilder().build(c)
        assert "prompt" in result
        assert "debug" in result
        assert isinstance(result["prompt"], str)

    def test_contains_character_name(self, db):
        c = Character.objects.create(name="Kaya", description="A young wolf")
        prompt = PromptBuilder().build(c)["prompt"]
        assert "You are Kaya." in prompt

    def test_core_traits_pinned(self, db):
        c = Character.objects.create(name="Kaya", description="")
        Trait.objects.create(name="brave", weight=9.0, character=c, is_core=True)
        result = PromptBuilder().build(c)
        assert "Core Traits (fixed):" in result["prompt"]
        assert "brave (9.0)" in result["prompt"]
        assert "brave (9.0)" in result["debug"].get("core_traits", "")

    def test_active_traits_top5(self, db):
        """Only the top 5 non-core traits by weight are listed."""
        c = Character.objects.create(name="Kaya", description="")
        for i in range(8):
            Trait.objects.create(name=f"trait{i}", weight=float(i), character=c)
        result = PromptBuilder().build(c)
        prompt = result["prompt"]
        assert "Current Traits:" in prompt
        # highest weights first
        assert "trait7" in prompt
        assert "trait3 (3.0)" in prompt
        # trait2 (weight 2) must be cut: only top 5 (3,4,5,6,7)
        assert "trait2 (2.0)" not in prompt
        assert "trait1 (1.0)" not in prompt

    def test_no_trait_sections_when_empty(self, db):
        c = Character.objects.create(name="Kaya", description="")
        prompt = PromptBuilder().build(c)["prompt"]
        assert "Core Traits" not in prompt
        assert "Current Traits" not in prompt

    def test_personality_voice_sections(self, db):
        c = Character.objects.create(
            name="Kaya", description="",
            personality={"voice": "warm", "quirks": "tail flicks",
                         "backstory": "grew up in the forest"},
        )
        result = PromptBuilder().build(c)
        assert "Personality:" in result["prompt"]
        assert "voice: warm" in result["prompt"]
        assert "quirks: tail flicks" in result["prompt"]
        assert "backstory: grew up in the forest" in result["prompt"]

    def test_world_context_injected(self, db):
        c = Character.objects.create(name="Kaya", description="")
        prompt = PromptBuilder().build(
            c, world_context="Ardania: A fantasy world."
        )["prompt"]
        assert "World: Ardania" in prompt

    def test_no_world_section_when_empty(self, db):
        c = Character.objects.create(name="Kaya", description="")
        prompt = PromptBuilder().build(c)["prompt"]
        assert "World:" not in prompt

    def test_memories_injected(self, db):
        c = Character.objects.create(name="Kaya", description="")
        result = PromptBuilder().build(
            c,
            memories={"documents": [["Kaya loves fish.", "Kaya saved a child."]]},
        )
        assert "Relevant Memories:" in result["prompt"]
        assert "Kaya loves fish." in result["prompt"]
        assert "Kaya saved a child." in result["prompt"]

    def test_no_memories_section_when_empty(self, db):
        c = Character.objects.create(name="Kaya", description="")
        prompt = PromptBuilder().build(c)["prompt"]
        assert "Relevant Memories" not in prompt

    def test_scenario_injected(self, db):
        c = Character.objects.create(name="Kaya", description="")
        result = PromptBuilder().build(
            c,
            scenario=[{
                "scenario_name": "Village Fire",
                "condition": "fire",
                "action": "React to the fire",
            }],
        )
        prompt = result["prompt"]
        assert "Active Scenarios:" in prompt
        assert "Scenario 'Village Fire'" in prompt
        assert "React to the fire" in prompt

    def test_conversation_history_injected(self, db):
        c = Character.objects.create(name="Kaya", description="")
        result = PromptBuilder().build(
            c,
            conversation=[("Hello there.", "Hey! How are you?")],
        )
        prompt = result["prompt"]
        assert "Recent Conversation:" in prompt
        assert "User: Hello there." in prompt
        assert "You: Hey! How are you?" in prompt

    def test_conversation_chronological(self, db):
        """History is rendered in chronological order."""
        c = Character.objects.create(name="Kaya", description="")
        prompt = PromptBuilder().build(
            c,
            conversation=[("First.", "A1"), ("Second.", "B2")],
        )["prompt"]
        assert prompt.index("User: First.") < prompt.index("User: Second.")

    def test_token_budget_limits_history(self, db):
        """With a tiny token budget, conversation turns get dropped."""
        c = Character.objects.create(name="Kaya", description="")
        long_turn = ("word " * 100).strip()
        result = PromptBuilder(max_tokens=50).build(
            c,
            conversation=[("Hello there.", long_turn)],
        )
        assert "Relevant Memories" not in result["prompt"]
        # the long turn must not fit in 50 tokens
        assert "word word" not in result["prompt"]

    def test_global_instructions_injected(self, db):
        c = Character.objects.create(name="Kaya", description="")
        gc_service.set_global_instructions(["Stay in character.", "No meta talk."])
        result = PromptBuilder().build(c)
        assert "Global Rules:" in result["prompt"]
        assert "Stay in character." in result["prompt"]
        assert result["debug"].get("global_rules") == ["Stay in character.", "No meta talk."]


# ---------------------------------------------------------------------------
# LLMClient
# ---------------------------------------------------------------------------

def _mock_urlopen(response_text, status=200):
    """Build a context manager mocking urllib.request.urlopen."""
    if status >= 400:
        import urllib.error
        exc = urllib.error.HTTPError(
            url="http://localhost/v1/chat/completions",
            code=status, msg="Error",
            hdrs={}, fp=MagicMock(),
        )
        cm = MagicMock()
        cm.__enter__.return_value = None
        cm.__exit__.side_effect = exc
        return cm
    resp = MagicMock()
    resp.status = status
    resp.read.return_value = json.dumps(
        {"choices": [{"message": {"content": response_text}}]}
    ).encode("utf-8")
    cm = MagicMock()
    cm.__enter__.return_value = resp
    cm.__exit__.return_value = False
    return cm


class TestLLMClient:
    def test_generate_success(self, db):
        """generate() returns the LLM reply text on 200."""
        client = LLMClient(base_url="http://localhost:9/v1", api_key="k", model="m")
        with patch("characters.llm.urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = _mock_urlopen("Hello from the LLM!")
            result = client.generate("Hi")
        assert result == "Hello from the LLM!"
        assert mock_urlopen.called

    def test_generate_handles_http_error(self, db):
        """An HTTP error returns [LLM Error: ...] without raising."""
        client = LLMClient(base_url="http://localhost:9/v1", api_key="k", model="m")
        with patch("characters.llm.urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = _mock_urlopen("boom", status=500)
            result = client.generate("Hi")
        assert result.startswith("[LLM Error:")

    def test_generate_handles_connection_error(self, db):
        """URLError (connection failure) is caught and returned as string."""
        import urllib.error
        client = LLMClient(base_url="http://localhost:9/v1", api_key="k", model="m")
        with patch("characters.llm.urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.side_effect = urllib.error.URLError("no route to host")
            result = client.generate("Hi")
        assert result.startswith("[LLM Error:")

    def test_generate_handles_malformed_response(self, db):
        """A missing 'choices' key yields [LLM Error: ...] (KeyError path)."""
        client = LLMClient(base_url="http://localhost:9/v1", api_key="k", model="m")
        resp = MagicMock()
        resp.read.return_value = b'{"no_choices": true}'
        cm = MagicMock()
        cm.__enter__.return_value = resp
        cm.__exit__.return_value = False
        with patch("characters.llm.urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = cm
            result = client.generate("Hi")
        assert result.startswith("[LLM Error:")

    def test_default_base_url(self, db):
        """Without LLM_BASE_URL, the default vLLM URL is used."""
        saved = os.environ.pop("LLM_BASE_URL", None)
        try:
            client = LLMClient()
            assert client.base_url == "http://localhost:8001/v1"
        finally:
            if saved is not None:
                os.environ["LLM_BASE_URL"] = saved

    def test_env_base_url_wins(self, db):
        """LLM_BASE_URL from the environment wins over the default."""
        saved = os.environ.get("LLM_BASE_URL")
        os.environ["LLM_BASE_URL"] = "http://example.com:1234/v1"
        try:
            client = LLMClient()
            assert client.base_url == "http://example.com:1234/v1"
        finally:
            if saved is not None:
                os.environ["LLM_BASE_URL"] = saved
            else:
                os.environ.pop("LLM_BASE_URL", None)

    def test_payload_shape(self, db):
        """The JSON payload matches the OpenAI chat/completions contract."""
        client = LLMClient(base_url="http://localhost:9/v1", api_key="sekret", model="my-model")
        with patch("characters.llm.urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = _mock_urlopen("ok")
            client.generate("Hi there")
        request_obj = mock_urlopen.call_args[0][0]
        assert request_obj.full_url == "http://localhost:9/v1/chat/completions"
        payload = json.loads(request_obj.data.decode("utf-8"))
        assert payload["model"] == "my-model"
        assert payload["messages"] == [{"role": "user", "content": "Hi there"}]
        assert payload["temperature"] == 0.8
        assert payload["max_tokens"] == 2048
        assert request_obj.headers["Authorization"] == "Bearer sekret"

    def test_system_prompt_prepended(self, db):
        """A system prompt becomes the first message."""
        client = LLMClient(base_url="http://localhost:9/v1", api_key="k", model="m")
        with patch("characters.llm.urllib.request.urlopen") as mock_urlopen:
            mock_urlopen.return_value = _mock_urlopen("ok")
            client.generate("Hi", system="You are Kaya.")
        payload = json.loads(mock_urlopen.call_args[0][0].data.decode("utf-8"))
        assert payload["messages"] == [
            {"role": "system", "content": "You are Kaya."},
            {"role": "user", "content": "Hi"},
        ]


class TestHybridLLMClient:
    def test_uses_primary_on_success(self):
        primary = MagicMock()
        primary.generate.return_value = "from primary"
        fallback = MagicMock()
        hybrid = HybridLLMClient(primary, fallback)
        assert hybrid.generate("hi") == "from primary"
        fallback.generate.assert_not_called()

    def test_falls_back_on_error(self):
        primary = MagicMock()
        primary.generate.return_value = "[LLM Error: down]"
        fallback = MagicMock()
        fallback.generate.return_value = "from fallback"
        hybrid = HybridLLMClient(primary, fallback)
        assert hybrid.generate("hi") == "from fallback"

    def test_no_fallback_available(self):
        primary = MagicMock()
        primary.generate.return_value = "[LLM Error: down]"
        hybrid = HybridLLMClient(primary)
        assert hybrid.generate("hi") == "No response from any LLM."
