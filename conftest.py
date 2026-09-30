"""
Pytest configuration.

Mocks chromadb before memory.services is imported, so tests run without
a running Chroma instance. Embedding calls are an OpenAI-compatible HTTP
endpoint (see memory/services.py); tests never reach it because the
engine is mocked. LLM calls are mocked per test; the env vars below only
keep the LLMClient construction from failing during imports.
"""
import os
import sys
from unittest.mock import MagicMock

# --- Mock chromadb before any import of memory.services ---
# memory.services does `from chromadb.utils import embedding_functions`,
# so each submodule must exist as a real module entry in sys.modules.
import types

_chromadb = MagicMock()
_chromadb.PersistentClient = MagicMock()

def _submodule(name):
    m = MagicMock()
    m.__spec__ = None
    return m

_utils = _submodule("chromadb.utils")
# memory.services does `from chromadb.utils import embedding_functions`
# and subclasses embedding_functions.EmbeddingFunction — the MagicMock
# attribute is subclassable, so a bare module mock is sufficient.
_ef = _submodule("chromadb.utils.embedding_functions")
_utils.embedding_functions = _ef
_chromadb.utils = _utils

sys.modules["chromadb"] = _chromadb
sys.modules["chromadb.utils"] = _utils
sys.modules["chromadb.utils.embedding_functions"] = _ef

# --- Embedding endpoint: tests never call it, but keep the config
# --- deterministic (memory.services reads these at import time). ---
os.environ.setdefault("EMBED_BASE_URL", "http://127.0.0.1:7997")
os.environ.setdefault("EMBED_MODEL", "BAAI/bge-m3")
os.environ.setdefault("EMBED_API_KEY", "")

# --- LLM env vars: no real server needed (tests mock LLMClient) ---
os.environ.setdefault("LLM_BASE_URL", "http://localhost:8000/v1")
os.environ.setdefault("LLM_API_KEY", "test-key")
os.environ.setdefault("LLM_MODEL", "test-model")

# --- Django env vars: settings.py is env-based (prod hardening) ---
# Tests run with DEBUG=true (as before) + a test secret + testserver host.
os.environ.setdefault("DJANGO_DEBUG", "true")
os.environ.setdefault("DJANGO_SECRET_KEY", "test-secret-key")
os.environ.setdefault("DJANGO_ALLOWED_HOSTS", "testserver,localhost,127.0.0.1")
