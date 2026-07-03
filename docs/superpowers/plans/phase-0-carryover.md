# Phase 0 → Later Phases — Carryover Notes

Deferred items surfaced during Phase 0 review. None are Phase 0 defects; each is deliberately out of Phase 0 scope. Address in the noted phase.

## Deployment hardening (before any prod deploy)
- **`config/settings/prod.py` must fail-closed on `SECRET_KEY`.** `base.py` defaults `SECRET_KEY` to `"dev-insecure-change-me"`; `prod.py` doesn't override or assert it. A prod boot with `SECRET_KEY` unset would silently use a public key. Add an explicit required-env check in `prod.py`.
- **Docker stack currently runs `config.settings.dev` (DEBUG=True) in every service** — `compose.yaml` sets no `DJANGO_SETTINGS_MODULE`, so containers fall back to the dev default. Fine for Phase 0's "compose up" goal; set `DJANGO_SETTINGS_MODULE=config.settings.prod` (and real `SECRET_KEY`/`ALLOWED_HOSTS`) for deployment.

## Phase 1 wiring
- **`worker` and `beat` services leave `REDIS_URL` at the `.env` `localhost` value** — their `environment:` blocks override `CELERY_BROKER_URL`/`CELERY_RESULT_BACKEND` but not `REDIS_URL`, so Django `CACHES` in those containers points at `localhost:6379/1`, not the `redis` service. Harmless now (worker/beat don't use the Django cache), but fix when the worker/bot start using cache or Redis-backed FSM. (`bot` already overrides `REDIS_URL` correctly — copy that.)

## Optional polish (any later touch of these files)
- `import_words.py` / `sync_audio.py`: use `if opts["book"] is not None` instead of truthiness (so `--book 0` isn't silently "all books"); add a malformed-fixture-record guard in `import_words`; log `sync_audio` non-200 remote misses.
- `Book.level`: add CEFR `choices` (A1..C1) per the design spec if levels get used.
- Dev `pytest` emits a whitenoise "No directory at: staticfiles/" warning — dev-only cosmetic; silence if desired.
- `config/settings/base.py`: flatten the eager inner `env()` in the `CELERY_BROKER_URL` default; fix the stale "email" docstring in `accounts/managers.py`.
