# Runtime Stabilization Design

## Goal

Prevent one slow summary request from blocking the Telegram bot or FastAPI service, without changing the user-facing commands or response format.

## Scope

This first phase makes synchronous work safe to call from async handlers, bounds external waits, and makes MongoDB persistence optional. It deliberately does not introduce a queue broker or split every concern out of `main.py`.

## Design

### Async boundary

Add a small async helper that runs existing synchronous functions in a thread using `asyncio.to_thread`. Telegram handlers and the FastAPI route will await this helper whenever they invoke URL extraction, subtitle/audio processing, LLM summarization, title lookup, Discord delivery, email delivery, or MongoDB persistence.

The existing synchronous implementations remain unchanged at their public boundary in this phase. This keeps command behaviour and error messages stable while ensuring CPU, subprocess, and blocking HTTP work cannot occupy the event loop.

### External request limits

Introduce named configuration values for HTTP connect/read timeouts and subprocess timeout. Apply them to LLM, Discord, Telegram command registration, and transcription calls. A timeout produces the existing error path rather than waiting indefinitely.

### Optional persistence

Only construct a MongoDB collection when `MONGO_URI` is configured. Persistence becomes a no-op when disabled. When configured, use bounded MongoDB connection timeouts. A failed write is logged and must not prevent the summary from being returned.

### Testing

Use `unittest` and standard-library mocks so tests run without live Telegram, LLM, MongoDB, Chrome, or external network services. Tests will verify that the new boundary offloads synchronous work, request helpers receive timeouts, and persistence is skipped when no database is configured.

## Non-goals

- Adding Redis, Celery, RQ, or another durable job queue.
- Changing Telegram commands, summary formatting, or API schemas.
- Rewriting all modules immediately; service extraction follows after this stabilisation phase.

## Acceptance criteria

1. Long-running synchronous summarization work does not run on the async event loop.
2. External LLM and webhook calls have finite time limits.
3. Missing `MONGO_URI` cannot cause summary handling to stall or fail.
4. New automated tests pass without requiring production credentials or containers.
