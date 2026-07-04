# 4000 Essential Words — Bot + Web App

Telegram bot + Django web app for learning the *4000 Essential English Words*.
See `docs/superpowers/specs/` for the product vision and phase specs.

## Stack
Python 3.13 · Django 6 · uv · PostgreSQL · Redis · Celery · django-unfold · Docker Compose.

## Local development

```bash
# 1. Install deps (uv)
python -m pip install --user uv
uv sync
# NOTE: if `uv` isn't on your PATH (common with `pip install --user`,
# especially on Windows), prefix every `uv ...` command below with
# `python -m`, e.g. `python -m uv sync`, `python -m uv run pytest`.

# 2. Config
cp .env.example .env

# 3. Infra
docker compose up -d db redis

# 4. Migrate + create admin
uv run python manage.py migrate
uv run python manage.py createsuperuser   # phone like 998901234567

# 5. Import content (~4000 words + images)
uv run python manage.py import_words
uv run python manage.py sync_audio         # optional; native mp3 + gTTS fallback

# 6. Run
uv run python manage.py runserver
```

Admin: http://localhost:8000/admin/

## Bot (Telegram)

Set `BOT_TOKEN` in `.env` (get one from @BotFather), then:

```bash
docker compose up -d db redis
python -m uv run python manage.py migrate
python -m uv run python -m bot          # long-polling bot
```

Send `/start` to your bot to register and run onboarding; `/settings` to edit.
Full stack (bot in Docker): `docker compose up --build bot`.

## Daily delivery (Phase 2a)

After migrating, register the recurring Beat task once:

```bash
python -m uv run python manage.py setup_periodic_tasks
```

The `worker` + `beat` compose services then deliver each user's words at their
configured `morning_time` (on their `study_weekdays`, in their timezone).
Audio combining needs `ffmpeg` (bundled in the Docker image; install locally if
running the worker outside Docker).

The `worker` + `beat` services also run the evening exam: at each user's
`exam_time`, `dispatch_evening_exams` sends native quiz polls over the day's
words (+ SRS-due reviews); the bot's poll-answer handler grades them and
updates each word's SM-2 schedule; `finalize_due_exams` closes the session
after `EXAM_WINDOW_MINUTES` and sends the daily report.

## Group quiz

Add the bot to a Telegram group and make it an **admin**. In @BotFather run
`/setprivacy` → **Disable** so the bot receives group commands. Then a group
admin sends `/quiz` and follows the wizard (book → units → question types →
count → interval) to start a QuizBot-style quiz; the bot posts sequential quiz
polls and a leaderboard ranking each student by correct answers then speed.
`/stop` aborts a running quiz.

## Parent / Teacher reports

A parent or teacher sends `/parent` (or `/teacher`) to the bot to get a
one-time deep-link (`t.me/<bot>?start=g...`). They forward it to their
child/student, who taps it to connect. The guardian then gets a daily
progress report (words learned, exam score, streak) at `GUARDIAN_REPORT_HOUR`,
and can request it any time with `/report`. (Run `setup_periodic_tasks` once
after migrating to register the daily job.)

## Full stack (Docker)

```bash
docker compose up --build
docker compose exec web python manage.py import_words
```

## Tests

```bash
docker compose up -d db redis
uv run pytest
uv run ruff check .
```
