# Phase 2a → Later Phases — Carryover Notes

Deferred items surfaced during Phase 2a review. None are Phase 2a defects; each is out of scope or a deliberate MVP tradeoff. Address in the noted phase.

## Deployment
- **`audioop-lts` is REQUIRED on Python 3.13+.** `pydub` imports the `audioop` stdlib module, which PEP 594 removed in 3.13; the `audioop-lts` backport (added, marker `python_full_version >= '3.13'`) restores it. Without it `from pydub import AudioSegment` crashes at import → the whole app fails to boot. Keep it in deps; ensure the Docker image / any deploy env installs it.
- **ffmpeg** is required at runtime for `pydub` audio combining (bundled in the Docker image via `apt-get install ffmpeg`). A worker running outside Docker needs ffmpeg on PATH.

## Phase 2b wiring
- **Concurrency double-send window in `run_delivery`.** The `status == DELIVERED` check → `send_daily` → mark-delivered is not row-locked/atomic. If Beat double-enqueues within the target minute or `acks_late` re-runs a task, two calls could both read PENDING and both send (duplicate messages). No data corruption (`UniqueConstraint(user,date)` prevents dup sessions; `get_or_create` prevents dup SessionWord/WordProgress). Harden with `select_for_update` on the session + `transaction.atomic` around advance+mark when convenient — do this before scale.
- **No-content path leaves a PENDING `DailySession`.** When a user finishes all words, each study-day creates one empty PENDING session and sends nothing (the plan's sample-vs-test contradiction was resolved toward the test = silent + return None). Consider a distinct "finished" status or skipping session creation until `next_words` is confirmed non-empty; optionally a one-time "course finished 🎉" notification (avoid daily spam).

## Quality / polish
- **gTTS Uzbek ('uz') support is uncertain.** `_uzbek_segment` is best-effort: any exception → logs a warning and degrades to EN-only audio. If Uzbek audio quality/support is poor, swap in a better TTS via the Phase-0 pluggable `TTS_PROVIDER` (e.g. a paid provider). Add a real ffmpeg/gTTS integration smoke test for `_render_combined` (currently mocked at the edge).
- **Untested guard branches in `run_delivery`**: `audio_enabled=False`, `blocked_bot=True` (pre-set), missing `TelegramAccount`, inactive/not-onboarded — implemented, but not exercised by tests. Add coverage on next touch.
- **Card width fixed at 720px** (`render_daily_card`) — long Uzbek translations could overflow. Make width content-aware or wrap text if it becomes a visible problem.
- Sender/deliver tests assert call **counts**, not arguments — a malformed `items`/wrong `chat_id` would pass silently. Strengthen with argument assertions when convenient.
