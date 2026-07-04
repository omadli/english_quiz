# Phase 4a → Later Phases — Carryover Notes

Deferred items from the Phase 4a (Roles/referral/reports) review. None are defects; the final whole-branch review confirmed the feature is correctly wired and merge-ready, and the one strongly-recommended follow-up (a security-path test for `pick_ward_report`) was ADDED before merge (teeth-verified). The rest below are genuine defers.

## Hardening (before scale)
- **`redeem_token` has no `select_for_update`.** Concurrent double-redemption of the same one-time token could race, but the `Guardianship` unique constraint on `(guardian, learner)` makes it idempotent (no duplicate link), and personal one-time links are near-zero concurrency. Add row-locking if it ever matters.
- **`dispatch_guardian_reports` sends sequentially in one task**, and its `blocked_bot=True` / no-`TelegramAccount` skip paths are untested. Both are single-`continue` guards; add coverage + consider per-guardian `.delay()` fan-out (like the delivery/exam dispatchers) if guardian counts grow.
- **`compute_streak` loads all of a learner's completed-session dates into memory.** Bounded by study days today; query a bounded window if it grows.

## Quality / correctness edges
- **`build_learner_report` treats `total == 0` like `None`** (`if session.total:`) — the exam line is omitted for a zero-question session. Use `is not None` if a 0-question exam is ever a real state.
- **`pick_ward_report` does `int(callback.data.split(":")[-1])`** with no guard — a non-numeric `rep:` payload would raise `ValueError`. Not exploitable (callback_data is bot-generated), but wrap defensively if desired.
- **`Role` TextChoices duplicated** across `ReferralToken` and `Guardianship` — extract a shared choices class when convenient.

## Test-coverage gaps (add on next touch)
- No `cmd_teacher`-specific test (same `_send_link` path as `/parent`, different constant); `cmd_parent` test doesn't assert the role arg.
- No invalid/expired-token test at the `cmd_start` layer (the `None` case is covered at the service layer).
- Weak assertions: `test_report_no_wards` / `cmd_parent` deep-link assert content loosely.
- Multi-ward branch of `cmd_report` (the `wards_keyboard` picker) is untested.

## Timezone
- Daily guardian reports fire at a single `GUARDIAN_REPORT_HOUR` (Asia/Tashkent) crontab; `compute_streak`/report use `timezone.localdate()`. Per-guardian timezone is a future refinement (guardians may not have a LearningProfile with a tz).
