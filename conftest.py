"""
Pytest configuration.

Mocks heavy ML dependencies (chromadb, sentence_transformers) before
memory.services is imported, so tests run without BGE-m3 or a running
Chroma instance. LLM calls are mocked per test; the env vars below only
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
_ef = _submodule("chromadb.utils.embedding_functions")
_ef.SentenceTransformerEmbeddingFunction = MagicMock(return_value=MagicMock())
_utils.embedding_functions = _ef
_chromadb.utils = _utils

sys.modules["chromadb"] = _chromadb
sys.modules["chromadb.utils"] = _utils
sys.modules["chromadb.utils.embedding_functions"] = _ef

# --- Mock sentence_transformers (same reason) ---
sys.modules.setdefault("sentence_transformers", MagicMock())

# --- LLM env vars: no real server needed (tests mock LLMClient) ---
os.environ.setdefault("LLM_BASE_URL", "http://localhost:8000/v1")
os.environ.setdefault("LLM_API_KEY", "test-key")
os.environ.setdefault("LLM_MODEL", "test-model")
