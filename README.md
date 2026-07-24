# Palworld Local LLM Companion

Local-first AI assistance for Palworld, grounded in real game data instead of guesses.
It combines Ollama, vector retrieval over user-provided game-data exports, optional
live server context, and web search for current guides and strategies.

## What it answers

- Where a Pal, material, dungeon, or resource can be found
- Practical routes using in-game map coordinates
- Capture, breeding, combat, and base-building strategies
- Live player positions from a server you administer
- Questions affected by recent patches, with web links

Every answer carries sources and a confidence level. When retrieval is weak, the
companion says it lacks evidence rather than inventing coordinates.

## Surfaces

- `pal-companion ask "Where can I get coal?"`
- Local HTTP `POST /ask` for PAL COMMAND and overlays
- Discord `/askpal`
- Future non-invasive desktop overlay; no game-process injection is required

## Architecture

```text
Question
  |
  +-- local vector index (exported game tables and curated notes)
  +-- live Palworld REST context (optional, read-only)
  +-- Brave web search (optional, current strategies and patches)
  |
Evidence pack with source IDs
  |
Local Ollama model
  |
Answer + citations + confidence
```

Ollama provides both the local chat model and embeddings. The starter index uses
SQLite and cosine similarity so the system has no external database service. The
storage interface can later move to Qdrant or another vector database without changing
the answer pipeline.

## Quick start

Requirements: Python 3.11+, Ollama, and an Ollama chat and embedding model.

```powershell
git clone https://github.com/luibots/palworld-local-llm-companion
cd palworld-local-llm-companion
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"

ollama pull qwen2.5:14b
ollama pull embeddinggemma

Copy-Item .env.example .env
pal-companion ingest data\samples\pals.jsonl
pal-companion ask "What is Lamball?"
```

Run the API:

```powershell
pal-companion api
```

```http
POST http://127.0.0.1:8765/ask
Content-Type: application/json

{"question":"Where can I get coal?","allow_web":true,"include_live":true}
```

Run Discord after putting the token only in local `.env`:

```powershell
pal-companion discord
```

## Data ingestion

JSONL records use this shape:

```json
{"source_id":"items:coal","title":"Coal","text":"Verified facts and coordinates","kind":"game-data","url":null,"metadata":{"game_version":"1.0"}}
```

Do not commit extracted copyrighted game data. Keep raw exports under `data/private/`;
that directory and the generated vector index are ignored. Publish extraction code,
schemas, and tiny clearly labeled examples instead.

## Integration boundaries

- Live Palworld calls are read-only.
- The companion does not inject into or patch the game process.
- Credentials stay in `.env`, which Git ignores.
- Web claims remain labeled and linked; they do not silently override game-table data.
- Server and player information must not be submitted to public issue reports.

## Status

The first vertical slice is implemented: Ollama chat/embeddings, SQLite vector retrieval,
live player coordinates, Brave search, FastAPI, Discord, CLI, and unit tests. Next work is
a robust game-table extraction pipeline and a polished PAL COMMAND companion panel.

## References

- [Ollama embeddings](https://docs.ollama.com/capabilities/embeddings)
- [Ollama API](https://docs.ollama.com/api/introduction)
- [Brave Search API](https://api-dashboard.search.brave.com/api-reference/web/search/get)
- [Discord application commands](https://docs.discord.com/developers/docs/interactions/slash-commands)

## License

MIT. Palworld is a trademark of Pocketpair, Inc. This project is unofficial and is not
affiliated with or endorsed by Pocketpair.
