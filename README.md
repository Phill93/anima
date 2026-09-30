# Anima RP System

**Breathing life into code.** 🐲

Anima is a local-first Role-Playing System where characters learn, remember, and evolve. It goes beyond static prompts by implementing persistent memory, trait evolution, and relationship dynamics.

## Architecture

- **Backend:** Django 5 + SQLite
- **Memory Engine:** ChromaDB (Embeddings via OpenAI-kompatible API, z.B. BGE-m3 auf vLLM/Infinity)
- **LLM Integration:** OpenAI-compatible API (vLLM, Ollama, etc.)
- **Focus:** Character growth, cross-session memory, and dynamic storytelling.

## Setup

1. **Clone & Install:**
   ```bash
   git clone https://github.com/Phill93/anima.git
   cd anima
   pip install django chromadb
   ```

2. **Migrations:**
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```

3. **Superuser:**
   ```bash
   python manage.py createsuperuser
   ```

4. **Embedding-Endpunkt:** Anima nutzt ein generisches OpenAI-kompatibles
   `/embeddings`-API (z.B. Infinity oder vLLM mit `BAAI/bge-m3`).
   Konfiguration via Umgebungsvariablen (Details in `.env.example`):
   `EMBED_BASE_URL` (Default `http://127.0.0.1:7997`), `EMBED_MODEL`,
   optional `EMBED_API_KEY`.

5. **Run Admin:**
   ```bash
   python manage.py runserver
   # Visit http://127.0.0.1:8000/admin
   ```

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