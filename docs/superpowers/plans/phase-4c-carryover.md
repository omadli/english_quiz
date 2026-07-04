# Phase 4c → Later Phases — Carryover Notes

Deferred items from the Phase 4c (Monthly-top leaderboard) review. None are defects; the final whole-branch review confirmed the metric aggregation, tiebreak, full-scan rank, and 8th-router wiring (factory + conftest) are all correct and merge-ready. The one flagged test-hygiene item (over-broad module `pytestmark asyncio` → 3 spurious warnings) was FIXED before merge (warnings 4→1). The rest below are genuine defers.

## Feature completeness (Phase 4c-follow / 4d)
- **Friend duels (Phase 4d):** the competitive chapter's second half — 1v1 challenge via deep-link/username, shared quiz, score+time comparison, winner. Reuses the group-quiz machinery (native quiz polls, poll_answer routing, scoring). Scope to confirm with the user.
- **Month-end broadcast:** an automatic end-of-month leaderboard push (crontab on day 1, each participant gets their final rank). Deferred — `/top` is on-demand only for now.

## Fairness & privacy (before wide rollout)
- **Metric is raw `Sum(score)` (correct-answer count):** learners who pick a larger `words_per_session` accumulate more points. Consider normalizing (accuracy %, or weighting consistency) for a fairer board (uzexam-style). Currently rewards volume + consistency (tiebreak by session count).
- **No privacy opt-out:** the leaderboard shows every completed-session learner's `first_name` + points. Add a `leaderboard_visible` toggle (mirror the `nudges_enabled` /settings pattern) if users want to be excluded.

## Test-coverage gaps (add on next touch)
- `test_leaderboard_limit` asserts only `len==3`, not WHICH 3 survive truncation (ordering is separately proven).
- `test_user_month_rank`'s beyond-top-10 assertion checks rank only, not the points value.
- The own-rank SUPPRESSION branch (caller inside top-N → no extra "your rank" line) is untested (the append + empty branches are).

## Config
- Leaderboard size is a `limit=10` default arg; promote to a `LEADERBOARD_SIZE` setting if it needs env tuning.
- Month boundary uses `timezone.localtime()` (Asia/Tashkent) matching `DailySession.date`; per-user tz would matter only for multi-tz users (same deferral as Phase 4a/4b).
