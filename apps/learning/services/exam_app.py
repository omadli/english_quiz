"""Sectioned Mini App exam (Quiz → Writing → Listening → Speaking).

The server grades: the client submits the answer TEXT it chose/typed/said, never
"correct/wrong", so it can't be faked. Grading reuses SM-2 (`grade_answer`, once
per word) and `finalize_exam` so streaks/dashboards/reports/leaderboard stay
consistent with the bot-poll exam.
"""

import random

from django.conf import settings
from django.utils import timezone

from apps.catalog.models import Word
from apps.learning.models import DailySession, ExamQuestion
from apps.learning.services.exam import _distractors, select_exam_words
from apps.learning.services.progress import mark_learned
from apps.learning.services.report import finalize_exam
from apps.learning.services.srs import grade_answer

_PUNCT = str.maketrans("", "", ".,;:!?\"'`()[]{}—–-/\\")
# section name -> (ExamQuestion type for the record, the Word field that is the answer)
_KIND_TYPE = {
    "quiz": ExamQuestion.QType.EN_UZ,
    "listening": ExamQuestion.QType.EN_UZ,
    "writing": ExamQuestion.QType.UZ_EN,
    "speaking": ExamQuestion.QType.UZ_EN,
}
_ANSWER_FIELD = {"quiz": "uz", "listening": "uz", "writing": "en", "speaking": "en"}


def _norm(s: str) -> str:
    return " ".join((s or "").lower().translate(_PUNCT).split())


def _mcq(word: Word, field: str) -> list[str]:
    opts = [getattr(word, field), *_distractors(word, field, 3)]
    random.shuffle(opts)
    return opts


def build_exam(session: DailySession, profile) -> dict:
    """The sectioned exam payload for the Mini App (no correct answers leaked)."""
    words = select_exam_words(session, settings.EXAM_REVIEW_CAP)
    if not words:
        return {"sections": []}

    def sample(n: int) -> list[Word]:
        return random.sample(words, min(n, len(words)))

    sections = [
        {"kind": "quiz", "questions": [
            {"word_id": w.id, "en": w.en, "pos": w.part_of_speech,
             "ipa": w.pronunciation, "options": _mcq(w, "uz")}
            for w in sample(5)
        ]},
        {"kind": "writing", "questions": [
            {"word_id": w.id, "uz": w.uz, "definition": w.definition,
             "len": len(w.en), "first": w.en[:1]}
            for w in sample(3)
        ]},
        {"kind": "listening", "questions": [
            {"word_id": w.id, "en": w.en, "options": _mcq(w, "uz")}
            for w in sample(3)
        ]},
    ]
    if profile and profile.speaking_enabled:
        sections.append({"kind": "speaking", "questions": [
            {"word_id": w.id, "en": w.en, "uz": w.uz, "ipa": w.pronunciation}
            for w in sample(3)
        ]})
    return {"sections": sections}


def _check(word: Word, kind: str, answer: str) -> bool:
    target = _norm(getattr(word, _ANSWER_FIELD[kind]))
    got = _norm(answer)
    if not target:
        return False
    if kind == "speaking":  # ASR is fuzzy — accept if the word is heard within the phrase
        return target in got or got in target
    return got == target


def submit_exam(session: DailySession, answers: list[dict]) -> dict:
    """Grade the Mini App exam server-side, apply SM-2 per word, finalize the session."""
    if session.status == DailySession.Status.COMPLETED:
        return {"score": session.score or 0, "total": session.total or 0, "already": True}

    words = {w.id: w for w in Word.objects.filter(id__in={a.get("word_id") for a in answers})}
    per_word: dict[int, list[bool]] = {}
    created = 0
    for a in answers:
        word = words.get(a.get("word_id"))
        kind = a.get("kind")
        if word is None or kind not in _ANSWER_FIELD:
            continue
        correct = _check(word, kind, a.get("answer", ""))
        ExamQuestion.objects.update_or_create(
            poll_id=f"app:{session.id}:{kind}:{word.id}",
            defaults={
                "daily_session": session, "word": word, "question_type": _KIND_TYPE[kind],
                "options": [], "correct_option": 0, "chosen_option": 0 if correct else 1,
                "is_correct": correct, "answered_at": timezone.now(),
            },
        )
        created += 1
        per_word.setdefault(word.id, []).append(correct)

    for wid, results in per_word.items():  # SM-2 once per word (correct iff right in every section)
        grade_answer(session.user, words[wid], all(results))

    # Completing the exam marks today's words 'learned' (same as the bot quiz),
    # so an early daytime attempt lifts the task to 'learned' status.
    mark_learned(session.user, list(per_word.keys()))

    session.total = created
    session.save(update_fields=["total", "updated_at"])
    finalize_exam(session)  # recomputes score from is_correct + COMPLETED + report + streak
    session.refresh_from_db()
    return {"score": session.score or 0, "total": session.total or 0}
