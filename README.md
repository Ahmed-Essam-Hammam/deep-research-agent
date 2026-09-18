# 🧱 Deep Research From Scratch

A production FastAPI service built on top of a multi-agent [LangGraph](https://www.langchain.com/langgraph) research system. Users register, open a conversation, and ask questions; the backend runs a **scope → research → write** agent pipeline (with pluggable LLM, embedding, and search providers) and streams the answer back over Server-Sent Events, with semantic + keyword response caching, JWT auth, and a Postgres/pgvector-backed persistence layer.

This repo started as a from-scratch tutorial on building a deep research agent with LangGraph and has grown into a full backend service around that agent: authentication, conversations, message history, a response cache, and a small static frontend under `pages/`.

---

## Table of contents

- [Architecture overview](#architecture-overview)
- [Project structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Quickstart — Docker (recommended)](#quickstart--docker-recommended)
- [Quickstart — local Python](#quickstart--local-python)
- [Configuration](#configuration)
- [Database & migrations](#database--migrations)
- [API reference](#api-reference)
- [Testing](#testing)
- [Linting & formatting](#linting--formatting)
- [CI/CD](#cicd)
- [Frontend (`pages/`)](#frontend-pages)

---

## Architecture overview

Research is an open-ended task — the right strategy and depth of search can't be known up front. Instead of a fixed pipeline, the system uses agents that can flexibly explore and adapt. The agent workflow has three phases:

1. **Scope** — clarify the user's request (asking a follow-up question if it's too ambiguous) and turn the conversation into a structured research brief.
2. **Research** — a supervisor agent delegates work to parallel research sub-agents, each running a ReAct-style tool-calling loop (web search via Tavily, `think` for reflection) up to a configurable number of iterations.
3. **Write** — the collected research findings are synthesized into a final report.

```
User message
     │
     ▼
┌──────────────┐     needs clarification?      ┌──────────────────┐
│   Scope      │ ───────────yes──────────────▶│ ask user, pause  │
│ (clarify +   │                               └──────────────────┘
│ write brief) │
└──────┬───────┘
       │ brief
       ▼
┌───────────────────────┐   ConductResearch()    ┌────────────────────┐
│  Supervisor subgraph  │ ─────────────────────▶│ Researcher subgraph │  (× N in parallel,
│ (delegates topics,    │◀───────────────────── │ (tool loop: search, │   up to
│  aggregates findings) │   findings             │  think, compress)  │   max_concurrent_researchers)
└──────────┬────────────┘                        └────────────────────┘
           │ ResearchComplete()
           ▼
┌────────────────────┐
│ Final report writer│
└──────────┬─────────┘
           │
           ▼
     Streamed response (SSE)
```

Around that agent core, the FastAPI app adds:

- **Auth** — JWT bearer tokens, bcrypt password hashing, register/login/logout/reset-password.
- **Conversations & messages** — persisted to Postgres; each message stores the prompt, the streamed response, and token usage.
- **Response cache** — before calling the LLM, recent messages are searched with both semantic similarity (pgvector cosine distance on embeddings) and Postgres full-text search, fused with Reciprocal Rank Fusion; a high-confidence match is served instead of re-running the agent.
- **Streaming** — chat responses are streamed to the client via `text/event-stream`.
- **Rate limiting** — per-IP limits (`slowapi`) on write endpoints, plus a global default of 200/day, 60/hour.
- **Pluggable providers** — LLM (`anthropic`, `openai`, `openrouter`), embeddings (`openrouter`), and search (`tavily`) are all swappable via a small factory/registry pattern (`src/providers/*/factory.py`), configured per-agent-role in `.env`.

## Project structure

```
.
├── main.py                      # FastAPI app factory, middleware, lifespan (DB init)
├── src/
│   ├── api/
│   │   ├── api_router.py        # Mounts all routers under /api
│   │   └── routers/             # health, auth, conversations, messages, research
│   ├── config/settings.py       # Pydantic Settings (reads .env)
│   ├── dependencies/            # DB session + engine, DI wiring for providers/services
│   ├── middleware/               # Request logging, slowapi rate limiter
│   ├── models/
│   │   ├── agents_states/       # LangGraph state schemas (scope, research, supervisor)
│   │   ├── db/                  # SQLAlchemy entities + Pydantic schemas
│   │   └── routes_schemes/      # Request/response models, in-memory task store
│   ├── prompts/prompts.py       # All agent prompt templates
│   ├── providers/               # llm/, embedding/, search/ — interface + implementations + factory
│   ├── repositories/            # DB access layer (users, conversations, messages, tokens)
│   ├── services/
│   │   ├── agents/
│   │   │   ├── graphs/          # researcher_graph, supervisor_graph, full_graph (compiled agent)
│   │   │   ├── nodes/           # scope_agent, research_agent, multi_agent node implementations
│   │   │   └── tools/           # think_tool, tavily_search tool
│   │   ├── auth.py, users.py, tokens.py, conversations.py, messages.py, search/
│   └── pipes/search_result_pipes.py  # Compression/report-generation helpers shared by graphs
├── pages/                       # Static HTML/CSS/JS frontend (login, register, chat UI)
├── alembic/, alembic.ini        # DB migrations
├── tests/                       # pytest suite (unit + integration, see tests/README.md)
├── Dockerfile, docker-compose.yml, .dockerignore
├── .github/workflows/ci.yml     # Lint → test → build & push Docker image
├── requirements.txt / pyproject.toml / uv.lock
└── langgraph.json                # Legacy LangGraph CLI/Studio graph config from the original
                                   # tutorial notebooks; not used by the FastAPI app itself
```

## Prerequisites

- **Docker + Docker Compose** (recommended path — see below), **or**
- **Python 3.11–3.13** and either [`uv`](https://docs.astral.sh/uv/) or `pip`, plus a local **PostgreSQL 17 with the `pgvector` extension** if not using Docker for the database.
- API keys for whichever providers you plan to use: [Tavily](https://tavily.com/) (search), and at least one of Anthropic / OpenAI / OpenRouter (LLM + embeddings — embeddings currently only support OpenRouter).

## Quickstart — Docker (recommended)

This spins up the API and a Postgres+pgvector database together.

```bash
git clone <this-repo-url>
cd deep_research_from_scratch

cp .env.example .env
# edit .env: fill in TAVILY_API_KEY, ANTHROPIC_API_KEY/OPENAI_API_KEY/OPENROUTER_API_KEY,
# and set SECRET_KEY_SIGN_TOKENS to a real random secret

docker compose up --build -d

curl http://localhost:8000/api/health   # {"status": "ok"}
```

The API is served at `http://localhost:8000/api/...`, and Postgres is exposed on `localhost:5400` (mapped from the container's `5432`) if you want to connect a DB client directly.

```bash
docker compose logs -f app     # tail app logs
docker compose down            # stop everything
docker compose down -v         # stop and wipe the Postgres volume
```

> ⚠️ **Note:** `init_db()` (run on every app startup, see `main.py`'s lifespan) currently does `drop_all` followed by `create_all` — every restart wipes and recreates all tables. This is convenient for iterating on the schema during development but means **no data currently persists across restarts**. Switch to driving the schema through Alembic migrations instead (see below) before relying on this for anything you want to keep.

## Quickstart — local Python

```bash
git clone <this-repo-url>
cd deep_research_from_scratch

# Using uv (manages the virtualenv for you)
uv sync
cp .env.example .env   # fill in your keys, and POSTGRES_URL for a local/remote Postgres

# Start just the database via Docker, if you don't have Postgres+pgvector locally
docker compose up -d pgvector

uv run uvicorn main:app --reload
```

Or with plain `pip`:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in your keys
docker compose up -d pgvector
uvicorn main:app --reload
```

The interactive API docs are then available at `http://localhost:8000/docs`.

## Configuration

All configuration is read from environment variables (or a `.env` file) via `src/config/settings.py`. See `.env.example` for the full list with defaults. Key groups:

| Group | Variables | Notes |
|---|---|---|
| Provider keys | `TAVILY_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `OPENROUTER_API_KEY` | Only the ones you actually use need to be set |
| Per-role LLM selection | `DEFAULT_LLM_PROVIDER`/`_MODEL`, `SCOPING_LLM_*`, `COMPRESSION_LLM_*`, `WRITER_LLM_*`, `SUMMARIZATION_LLM_*`, `SUPERVISOR_LLM_*`, `RESEARCHER_LLM_*` | Each agent role can use a different provider/model; default provider is `openrouter` |
| Search | `SEARCH_PROVIDER` (default `tavily`), `SEARCH_MAX_RESULTS`, `SEARCH_TOPIC`, `SEARCH_INCLUDE_RAW_CONTENT` | |
| Embeddings | `EMBEDDING_PROVIDER` (default `openrouter`), `EMBEDDING_MODEL`, `EMBEDDING_DIMENSIONS` | Used for the semantic response cache |
| Response cache | `CACHE_ENABLED`, `CACHE_LOOKBACK`, `CACHE_TOP_N_PER_METHOD`, `CACHE_RRF_K`, `CACHE_HIT_SCORE_THRESHOLD` | Tune how aggressively cached answers are served |
| Research limits | `MAX_RESEARCHER_ITERATIONS`, `MAX_CONCURRENT_RESEARCHERS`, `RESEARCHER_MAX_TOOL_CALLS_SIMPLE`/`_COMPLEX` | Controls depth/parallelism/cost of a research run |
| Auth | `ENCRYPTION_ALGORITHM` (e.g. `HS256`), `SECRET_KEY_SIGN_TOKENS`, `TOKEN_EXPIRATION_TIME_MINUTES` | **Set `SECRET_KEY_SIGN_TOKENS` to a real secret** before deploying anywhere |
| Database | `POSTGRES_URL` (or `POSTGRES_USER`/`PASSWORD`/`DB` when using docker-compose, which derives the URL for you) | Must be an `asyncpg` SQLAlchemy URL, e.g. `postgresql+asyncpg://user:pass@host:5432/db` |
| Tracing (optional) | `LANGSMITH_API_KEY`, `LANGSMITH_TRACING`, `LANGSMITH_PROJECT`, `LANGSMITH_ENDPOINT` | For [LangSmith](https://smith.langchain.com/) run tracing |

## Database & migrations

Schema is managed with [Alembic](https://alembic.sqlalchemy.org/); migrations live in `alembic/versions/`.

```bash
# Apply all migrations
alembic upgrade head

# Create a new migration after changing an entity in src/models/db/entities/
alembic revision --autogenerate -m "describe the change"

# Roll back one migration
alembic downgrade -1
```

`alembic.ini` points at a local default URL (`localhost:5400`) for convenience when running Alembic outside Docker; override it with `-x` or by setting `POSTGRES_URL` and adjusting `alembic/env.py` usage as needed for your environment.

## API reference

All routes are mounted under `/api`. Full interactive docs (Swagger UI) are at `/docs` once the app is running.

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/health` | Liveness check |
| `POST` | `/api/auth/register` | Create a new user |
| `POST` | `/api/auth/token` | Log in (OAuth2 password flow), returns a bearer token |
| `POST` | `/api/auth/logout` | Invalidate the current token |
| `POST` | `/api/auth/reset-password` | Change the authenticated user's password |
| `GET` | `/api/conversations` | List the current user's conversations (`skip`, `take` query params) |
| `POST` | `/api/conversations` | Create a conversation *(rate-limited: 5/min)* |
| `GET` | `/api/conversations/{id}` | Get one conversation |
| `PUT` | `/api/conversations/{id}` | Update a conversation *(rate-limited: 5/min)* |
| `DELETE` | `/api/conversations/{id}` | Delete a conversation *(rate-limited: 5/min)* |
| `GET` | `/api/conversations/{id}/messages` | List messages in a conversation |
| `POST` | `/api/conversations/{id}/messages` | Send a prompt; **streams** the agent's response as SSE *(rate-limited: 5/min)* |
| `POST` | `/api/research` | Kick off a standalone research run in the background, returns a `task_id` |
| `GET` | `/api/research/{task_id}` | Poll a research task's status/result |
| `DELETE` | `/api/research/{task_id}` | Drop a completed/failed task from memory |
| `POST` | `/api/research/test-llm` | Ad-hoc single-turn call to the OpenRouter provider, for debugging |

Authenticated routes expect `Authorization: Bearer <token>` from `/api/auth/token`.

## Testing

```bash
pip install -r requirements.txt -r tests/requirements-test.txt
pytest tests/ -v

# Skip tests that need a real Postgres+pgvector instance
pytest tests/ -v -m "not integration"
```

No `.env` is required — `tests/conftest.py` fills in safe dummy settings for anything read at import time. Integration tests (`@pytest.mark.integration`) run against a real database when `POSTGRES_URL` is reachable (e.g. `docker compose up -d pgvector`) and are otherwise skipped automatically; each runs inside a rolled-back transaction so nothing persists. See `tests/README.md` for the full breakdown of what each test file covers.

## Linting & formatting

```bash
# Formatting check
black --check .

# Linting (matches CI's threshold)
pylint --disable=R,C --fail-under=7.0 src/ pages/ tests/

# Ruff is also configured in pyproject.toml for import order / docstrings
ruff check src/
```

## CI/CD

`.github/workflows/ci.yml` runs on every push to `main` (and manually via `workflow_dispatch`):

1. **`lint`** — `pylint` against `src/`, `pages/`, `tests/`
2. **`test`** — `pytest` over the full test suite
3. **`build-and-push`** *(only after `lint` and `test` pass, on `main`)* — builds the image from the `Dockerfile` and pushes it to Docker Hub, tagged `latest` and with the short commit SHA

Requires the `DOCKERHUB_USERNAME` and `DOCKERHUB_TOKEN` repository secrets to be set for the push step.

## Frontend (`pages/`)

`pages/` is a minimal static frontend (no build step) that talks to the API: `index.html`, `login.html`, `register.html`, `reset-password.html`, and the main chat UI in `app.html`, sharing `shared.css`/`shared.js`. It's not currently served by the FastAPI app itself (no `StaticFiles` mount in `main.py`) — serve it separately (e.g. any static file server) pointed at this API, or open the files directly and configure the API base URL in `shared.js`.