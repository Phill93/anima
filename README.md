# Anima RP System

**Breathing life into code.** 🐲

Anima is a local-first Role-Playing System where characters learn, remember, and evolve. It goes beyond static prompts by implementing persistent memory, trait evolution, and relationship dynamics.

## Architecture

- **Backend:** Django 5 + SQLite
- **Memory Engine:** ChromaDB (BGE-m3 embeddings)
- **LLM Integration:** OpenAI-compatible API (vLLM, Ollama, etc.)
- **Focus:** Character growth, cross-session memory, and dynamic storytelling.

## Setup

Anforderungen: Python ≥ 3.11, [uv](https://docs.astral.sh/uv/) (oder pip).

1. **Clone & Install:**
   ```bash
   git clone https://github.com/Phill93/anima.git
   cd anima
   uv venv && uv pip install django django-celery-beat celery chromadb sentence-transformers
   # oder: pip install django django-celery-beat celery chromadb sentence-transformers
   source .venv/bin/activate
   ```

2. **Umgebungsvariablen:**
   ```bash
   cp .env.example .env   # dann füllen (LLM-Endpunkt + API-Key)
   ```
   Ohne `.env` greifen die eingebauten ki-toolbox-Defaults — für einen eigenen LLM-Endpunkt `LLM_BASE_URL`/`LLM_MODEL`/`LLM_API_KEY` setzen. Details in `.env.example`.

3. **Migrations:**
   ```bash
   python manage.py migrate
   ```

4. **Superuser:**
   ```bash
   python manage.py createsuperuser
   ```

5. **Run Admin:**
   ```bash
   python manage.py runserver
   # Visit http://127.0.0.1:8000/admin
   ```

6. **Celery (optional, für nächtliche Memory-Konsolidierung):**
   ```bash
   celery -A anima worker -B --loglevel=info   # Redis auf localhost:6379 nötig
   ```

> Hinweis: Beim ersten Start lädt `sentence-transformers` das BGE-m3-Embedding-Modell (~2 GB, einmalig).

## Usage

### Running a Session

Start an interactive RP session from the terminal:

```bash
python manage.py run_session --character <ID> --world <ID> --llm-url <API_URL> --llm-model <MODEL_NAME>
```

**Example:**
```bash
python manage.py run_session --character 1 --world 1 --llm-url "http://localhost:8001/v1" --llm-model "qwen3.6-27b"
```

## Features

- **Persistent Memory:** Memories are stored in ChromaDB for semantic retrieval and SQLite for archival.
- **Dynamic Traits:** Characters have Core (immutable) and Active (evolving) traits.
- **Two-Step Retrieval:** Keyword filtering + Semantic search for accurate context.
- **Deduplication:** Prevents redundant memories from bloating the context.

## Project Structure

- `characters/` - Character profiles, traits, prompt builder, LLM client.
- `anima_sessions/` - RP sessions, turns, and the management command runner.
- `memory/` - ChromaDB integration, memory models, retrieval logic.
- `worlds/` - World settings, locations, and lore.
- `scenarios/` - Starting situations and triggers.
- `relationships/` - Bidirectional character relationships.

## Roadmap

- [x] Phase 1: Base structure & Models
- [x] Phase 2: Memory Engine & Admin
- [x] Phase 3: Prompt Builder & LLM Client
- [ ] Phase 4: Trait Evolution & Condensation Logic
- [ ] Phase 5: Web UI / CLI Polish

---
*Built by Blacky 🐲 for Lurky.*