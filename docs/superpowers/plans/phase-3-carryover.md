# Phase 3 → Later Phases — Carryover Notes

Deferred items from the Phase 3 (Group quiz) review. None are Phase 3 defects; each is a scoped MVP tradeoff or polish item. The final whole-branch review confirmed the feature is correctly wired end-to-end and merge-ready. The one Important finding (wizard callbacks not admin-gated) was FIXED before merge.

## Feature completeness
- **`3-2-1-Go` countdown not implemented.** Spec §1/§4 and DoD §8 mention a countdown ("sanoq") before the first poll, but `run_group_quiz` goes straight from `prepare_questions` into the poll loop. Cosmetic; add a `send_message("3️⃣")` → `edit` "2️⃣/1️⃣/🚀" with `asyncio.sleep(1)` between, before the loop, if desired.

## Runner robustness (before scale)
- **`run_group_quiz` has no top-level try/except.** Only `send_poll`/`record_poll_sent` are guarded per-question. If `prepare_questions`, `finish_and_leaderboard`, or the final `send_message` raises, the exception escapes into the fire-and-forget `asyncio.create_task` and only surfaces as an unretrieved-task-exception log — leaving the `GroupQuizSession` stuck in `running` with no leaderboard. Recoverable by an admin `/stop` (which operates on `running` sessions). Wrap the runner body in try/except that logs + marks the session aborted/finished on failure.
- **Bot restart mid-quiz strands the session** in `running` (the in-memory `create_task` is lost). Spec §9 accepts this for MVP; recoverable via `/stop`. A future "resume/reap orphaned running sessions on startup" task could close it.
- **`_interval` fetched twice per question** (once for `open_period`, once for the trailing `sleep`) — one extra `sync_to_async` hop per question; fetch once and reuse.
- **`continue` on a failed poll skips the trailing `asyncio.sleep`** — a run of failures fires with no pacing/backoff. Add a small sleep on the error path if Telegram rate-limits become an issue.

## Data / quality
- **`GroupQuizQuestion.poll_id` is indexed but not DB-unique.** Safe today (Telegram poll_ids are globally unique, so `filter(poll_id=...).first()` is unambiguous), but a `unique=True` (partial, where poll_id is not null) would be a stronger guarantee.
- **`build_leaderboard` sorts in Python** (`sorted(...)`), not `order_by("-correct_count", "total_time")` — fine for ≤50 participants, DB-side would be more idiomatic.
- **Test-coverage gaps** (service layer is tested; these are handler/branch gaps): the 7 wizard callbacks + `/stop` have no handler-level tests (only `toggle_unit_cb`, `start_quiz` ownership, and services are covered); `build_leaderboard` empty/50-cap branches; `finish_and_leaderboard`'s "already aborted" branch; `record_group_answer`'s multi-question accumulation; the `username or ""` fallback. Add smoke tests on next touch.
- **Group-quiz strings are local module constants** in `bot/handlers/group_quiz.py` rather than in `bot/strings.py` (the project's house rule for UI text). Consolidate into `bot/strings.py` when convenient (i18n-readiness).
