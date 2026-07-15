"""
LLM integration - calls the model and returns the response.

Supports:
1. Local vLLM (primary)
2. KIT Toolbox (fallback)
"""
import os
import urllib.request
import urllib.error
import json


class LLMClient:
    """
    Generic LLM client that can call a local vLLM or external API.
    """
    def __init__(self, base_url: str = None, api_key: str = None, model: str = None):
        self.base_url = base_url or os.getenv("LLM_BASE_URL", "http://localhost:8001/v1")
        self.api_key = api_key or os.getenv("LLM_API_KEY", "")
        self.model = model or os.getenv("LLM_MODEL", "local-model")
        self.timeout = 120  # seconds

    def generate(self, prompt: str, system: str = None, temperature: float = 0.8, max_tokens: int = 2048) -> str:
        """
        Call the LLM and return the response text.
        """
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = json.dumps({
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode())
                return data["choices"][0]["message"]["content"]
        except (urllib.error.URLError, KeyError) as e:
            return f"[LLM Error: {e}]"


class HybridLLMClient(LLMClient):
    """
    Tries primary LLM first, falls back to secondary if it fails.
    """
    def __init__(self, primary: LLMClient, fallback: LLMClient = None):
        self.primary = primary
        self.fallback = fallback

    def generate(self, prompt: str, system: str = None, temperature: float = 0.8, max_tokens: int = 2048) -> str:
        try:
            result = self.primary.generate(prompt, system, temperature, max_tokens)
            if not result.startswith("[LLM Error"):
                return result
        except Exception:
            pass

        if self.fallback:
            return self.fallback.generate(prompt, system, temperature, max_tokens)

        return "No response from any LLM."