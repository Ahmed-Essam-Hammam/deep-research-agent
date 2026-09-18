# Tests

## Setup

```bash
pip install -r requirements.txt -r tests/requirements-test.txt
```

No `.env` is required to run the suite - `tests/conftest.py` sets safe dummy
values (`POSTGRES_URL`, `SECRET_KEY_SIGN_TOKENS`, dummy API keys, ...) for
every setting that's read at import time, *before* any project module gets
imported. Your real `.env` values, if present in the environment, are left
alone (`os.environ.setdefault` only fills in what's missing).

## Running

```bash
pytest tests/ -v
```

Run just the fast unit tests (skip anything needing a real database):

```bash
pytest tests/ -v -m "not integration"
```

## Two kinds of tests

- **Unit tests** (no marker): mock every collaborator (DB session,
  repositories, LLM/embedding/search providers). Fast, deterministic, run
  anywhere.
- **`@pytest.mark.integration`**: exercise real SQL against a real
  Postgres+pgvector instance - repository CRUD, pgvector's `cosine_distance`,
  Postgres full-text search, `init_db()`. These use the `db_session` fixture,
  which checks whether `POSTGRES_URL` is actually reachable and calls
  `pytest.skip(...)` if not - so the whole suite is safe to run whether or
  not `docker-compose up` (from the project root) is running. Each
  integration test runs inside a transaction that's rolled back afterward
  (via `join_transaction_mode="create_savepoint"`), so nothing written during
  a test persists.

## Layout

| File | Covers |
|---|---|
| `conftest.py` | Env setup, `db_available`/`db_session` fixtures, `integration` marker, small test-data helpers |
| `test_database.py` | `engine`/`async_session` config, `get_db_session()`, `init_db()` |
| `test_users.py` | Username/password validation, `UserRepository`, `UserService`, the user-facing half of `AuthService` |
| `test_conversations.py` | `ConversationRepository`, `ConversationService` (title generation/fallback) |
| `test_tokens.py` | `PasswordService` (real bcrypt), `TokenRepository`, `TokenService` |
| `test_messages.py` | `fuse_cache_candidates` (RRF), `MessageService` cache logic, the SSE streaming helpers, `MessageRepository` (pgvector + full-text search) |
| `test_search.py` | `TavilySearchProvider`, the search factory, `SearchService`, `SearchResultPipe` |
| `test_agents.py` | `ScopeAgent`, `ResearchAgent`, `MultiAgent` helpers, the `think_tool`/`tavily_search` tools, structured-output schemas |
| `test_providers.py` | LLM/embedding provider factories, `OpenRouterProvider`, `OpenRouterEmbeddingProvider` (mocked - no network) |

## Bugs this suite found (marked `xfail(strict=True)`)

Writing these tests surfaced three pre-existing bugs. Each is documented
in-line as an `xfail` test capturing the *intended* behavior, so the suite
stays green today but turns red (in a good way - `strict=True` fails the run
if an xfail unexpectedly starts passing) the moment someone fixes it and
forgets to remove the marker:

1. **`validate_password` never checks for uppercase/lowercase** (`test_users.py`) -
   `for condition, error_message in validations: ... return value` has the
   `return` inside the loop at the same indent as the `if`, so it returns
   after the *first* check (digit presence) passes, without ever evaluating
   the other two.
2. **`ConversationRepository.update` wipes `title` on a partial update**
   (`test_conversations.py`) - it calls `updated_conversation.model_dump()`
   without `exclude_unset=True` (every other repository's `update()` uses
   it), so a PUT that only sends `model_type` gets `title=None` applied too,
   since that's `ConversationUpdate.title`'s default.
3. **`TokenService.deactivate()` is broken, so `AuthService.logout()` is too**
   (`test_tokens.py`) - it calls `self.repository.update(TokenUpdate(id=token_id,
   is_active=False))` with one positional argument where
   `TokenRepository.update(token_id, updated_token)` needs two, and
   `TokenUpdate` requires `user_id`/`expires_at`, neither of which is
   supplied - so this raises a `pydantic.ValidationError` before ever
   reaching the repository.

## Worth double-checking locally

I couldn't install this project's dependencies or run pytest in the
sandbox this was written in (no network access), so everything here was
verified by careful reading and `py_compile`, not by execution. Two spots
worth a second look when you run the suite for real:

- `test_agents.py::test_tavily_search_tool_delegates_to_search_and_formatting_helpers`
  calls the LangChain `@tool`-decorated `tavily_search.invoke({...})` - the
  exact way LangChain fills in defaults for parameters not in the invoke
  dict (`summarization_model`, the `InjectedToolArg` ones) can shift between
  langchain-core versions.
- `tests/conftest.py`'s `db_session` fixture uses
  `AsyncSession(..., join_transaction_mode="create_savepoint")`, which needs
  a reasonably recent SQLAlchemy 2.x. If your installed version predates it,
  that fixture will raise a `TypeError` on setup for every integration test.
