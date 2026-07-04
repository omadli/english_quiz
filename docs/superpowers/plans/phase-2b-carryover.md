# Phase 2b → Later Phases — Carryover Notes

Deferred items surfaced during Phase 2b review. None are Phase 2b defects; each is out of scope, a deliberate MVP tradeoff, or a product-judgment call. The final whole-branch review confirmed the evening-exam pipeline is correctly wired end-to-end (poll_answer bridge live) and merge-ready.

## Product judgment (decide before Phase 2c / production)
- **Late poll answers after finalize.** The quiz poll `open_period` is intentionally omitted (Telegram caps it at 600s, but `EXAM_WINDOW_MINUTES` defaults to 60 min; `finalize_due_exams` is the real deadline). So a user can still answer a poll *after* `finalize_exam` marked the session `COMPLETED` and sent the report. Today that late answer still applies SM-2 and does `DailySession.score = F("score")+1`, so the stored score can drift above the already-reported figure (no new report is sent — cosmetic). Decision needed: should late answers count for SRS at all? If not, add a guard in `record_answer` (`skip if question.daily_session.status == COMPLETED`). If SRS-yes-but-score-no, guard only the score bump.

## Hardening (before scale)
- **`finalize_due_exams` has no row lock.** Overlapping beat runs could double-finalize a session (low probability — needs concurrent dispatch + slow finalize). Add `select_for_update(skip_locked=True)` on the `EXAM_SENT` queryset inside a transaction.
- **`record_answer` guard→update is not `select_for_update`.** A double-vote race could double-bump the running `F()` score — but Telegram quiz polls are answer-once and `finalize_exam` recomputes the authoritative score from the `is_correct=True` count, so the running score is throwaway. Low priority.
- **`grade_answer` (SM-2) has no locking** and `apply_sm2` calls `save()` writing all fields (not `update_fields`). Fine at current volume; revisit if it becomes a hot path.
- **`ease_factor` is uncapped**; over ~40 years of flawless reviews `interval_days` (`PositiveSmallInt`, max 32767) could theoretically overflow. Add an ease ceiling or clamp `interval_days` if this ever matters.
- **`run_exam` opens a fresh Bot session per question** (`send_quiz_poll` in a loop). Correct but inefficient; batch into one Bot session if poll volume grows.

## Test coverage gaps (add on next touch)
- `is_due_for_exam` has only 2 tests vs `is_due_for_delivery`'s 5 (no weekday/inactive/not-onboarded guard cases) — same logic, just thinner.
- `run_exam` None-return branches (no telegram account / `blocked_bot` / no words) are unexercised.
- SM-2 KNOWN→LEARNING downgrade path is untested (code is correct on inspection).
- Question generation: no `uz_en`/`def_word` correct-value identity tests; option-truncation distinctness-collapse and distractor-pool exhaustion are theoretical (unreachable with real single-word vocab / 4000-word catalog).
