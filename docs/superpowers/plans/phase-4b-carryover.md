# Phase 4b → Later Phases — Carryover Notes

Deferred items from the Phase 4b (Nudges & streaks) review. None are defects; the final whole-branch review confirmed the feature is correctly wired end-to-end (nudges_enabled honored in all four channels, anonymous practice poll isolated from grading, idempotency + mark-after-send correct, 7 Beat tasks registered without collision, cross-phase touches additive) and merge-ready. One Important during Task 2 (untested `due_pre_exam_nudges`/`mark_pre_exam_nudged`) was FIXED before merge (teeth-verified). The rest below are genuine defers.

## Timezone
- **`due_pre_exam_nudges` candidate-date filter hardcodes `Asia/Tashkent`** (`nudges.py`). The actual due-window check (`is_due_for_pre_exam_nudge`) IS per-profile-tz; only the coarse `date=today` pre-filter uses a fixed tz. Correct for the all-Tashkent default; refine to per-profile date when multi-tz users appear (same note as Phase 4a guardian reports).

## Test-coverage gaps (add on next touch)
- Dispatch tasks: the no-`TelegramAccount` / `blocked_bot` skip branches, `dispatch_pre_exam_nudges` end-to-end dispatch, and the "mark still fires when the send raises" behavior are untested (code correct by inspection; mirrors the proven Phase-2a/2b dispatch pattern).
- `test_setup_registers_nudge_tasks` asserts each task row exists but not that study/practice have `crontab is not None`/`interval is None` (a crontab↔interval swap would pass).
- `test_settings_present` asserts setting TYPES, not concrete default values (14/12/30/[3,7,14,30,50,100]).
- Streak-celebration + settings-toggle tests assert call-count / flip only, not the exact args (`send_daily` caption, `save(update_fields=...)`, False→True direction, keyboard row content).

## Micro-optimizations
- `pick_practice_word` does two DB round-trips (fetch word_ids, then `Word.objects.get`) — could be one query. Once-daily low-volume task, negligible.
- `is_due_for_pre_exam_nudge` duplicates `is_due_for_exam`'s is_active/onboarded/weekday guard verbatim (brief's "mirror" instruction) — extract a shared helper when convenient.
- `active_practice_learners` annotated `-> list` rather than `-> list[User]`; gate condition in `finalize_exam` uses a backslash line-continuation (cosmetic).

## Content polish
- Spec suggested multiple string variants per nudge type ("bir nechta variant bo'lsa yaxshi") for variety; single variants shipped (`NUDGE_STUDY`/`NUDGE_PRE_EXAM`/`NUDGE_STREAK`). Add rotating variants for freshness if desired.
