# App Package Refactor Design

## Goal

Move application code from the monolithic root `main.py` into an `app/` package without changing Telegram commands, FastAPI request/response schemas, supported environment variables, or the operational `build.sh` workflow.

## Architecture

`app.main` becomes the only production composition root. It constructs the Telegram application and Uvicorn server, while `app.bot` and `app.api` depend on shared services rather than importing one another.

```text
Telegram handlers ─┐
                   ├─> services ─> repositories / delivery
FastAPI route ─────┘
```

## Package layout

```text
app/
  __init__.py
  config.py                 # environment-backed Settings
  runtime.py                # async blocking-work adapter
  services/
    content.py              # text, web, video, podcast, and ASR extraction
    summarization.py        # prompts and LLM client
    delivery.py             # Discord and email delivery
    telegram_commands.py    # Telegram command registration HTTP calls
  repositories/
    summaries.py            # optional MongoDB persistence
  bot.py                    # Telegram handlers and Application factory
  api.py                    # FastAPI app and schema
  main.py                   # process startup and shutdown
main.py                     # compatibility entry point for local callers
api.py                      # compatibility export of app.api.app
```

## Configuration and dependencies

`Settings` reads the existing environment variables, including the current timeout fallback names. It is created once at startup and passed to services and repositories. This removes import-time MongoDB side effects and allows API and Bot to share exactly one configuration model.

## Reliability corrections included before/during migration

- Give Telegram command registration requests a bounded general-web timeout.
- Use `try/finally` for temporary subtitle, WAV, MP3, and downloaded podcast files.
- Update `build.sh` to require an explicit deployment confirmation before replacing an existing container.
- Copy `app/` as a package in Docker and run `python -m app.main`; avoid copying the whole repository into the image.

## Compatibility

- Telegram commands and messages remain unchanged.
- `POST /api/v1/summarize`, response fields, and authentication remain unchanged.
- Existing `.env` keys work unchanged.
- Root `main.py` delegates to `app.main`; root `api.py` re-exports the FastAPI app for external imports.

## Verification

Unit tests cover settings compatibility, temporary-file cleanup, Docker package copying, API-to-service calls, and root-wrapper imports. The final check compiles all package modules, runs the test suite, builds the Docker image, then verifies the remote host before deployment.
