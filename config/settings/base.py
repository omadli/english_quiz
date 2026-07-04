from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, ["*"]),
)
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY", default="dev-insecure-change-me")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env("ALLOWED_HOSTS")

INSTALLED_APPS = [
    "unfold",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_celery_beat",
    # local
    "apps.common",
    "apps.accounts",
    "apps.catalog",
    "apps.learning",
    "apps.quiz",
    "apps.relations",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

DATABASES = {"default": env.db("DATABASE_URL", default="sqlite:///" + str(BASE_DIR / "db.sqlite3"))}

CACHES = {"default": env.cache("REDIS_URL", default="locmemcache://")}

AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "uz"
LANGUAGES = [("uz", "O'zbekcha"), ("en", "English")]
LOCALE_PATHS = [BASE_DIR / "locale"]
TIME_ZONE = "Asia/Tashkent"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Celery
CELERY_BROKER_URL = env("CELERY_BROKER_URL", default=env("REDIS_URL", default="redis://localhost:6379/0"))
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default=CELERY_BROKER_URL)
CELERY_TIMEZONE = TIME_ZONE
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"

# Redis (bot FSM storage; see bot.config.get_fsm_redis_url)
REDIS_URL = env("REDIS_URL", default="redis://localhost:6379/1")

# Pluggable TTS
TTS_PROVIDER = env("TTS_PROVIDER", default="apps.common.tts.GTTSProvider")

# Telegram (Phase 1+)
BOT_TOKEN = env("BOT_TOKEN", default="")

# Evening exam (Phase 2b)
EXAM_WINDOW_MINUTES = env.int("EXAM_WINDOW_MINUTES", default=60)
EXAM_REVIEW_CAP = env.int("EXAM_REVIEW_CAP", default=10)

# Guardian reports & referral bot (Phase 4a)
GUARDIAN_REPORT_HOUR = env.int("GUARDIAN_REPORT_HOUR", default=21)
BOT_USERNAME = env("BOT_USERNAME", default="")

# Nudges & streaks (Phase 4b)
STUDY_NUDGE_HOUR = env.int("STUDY_NUDGE_HOUR", default=14)
PRACTICE_POLL_HOUR = env.int("PRACTICE_POLL_HOUR", default=12)
PRE_EXAM_NUDGE_MINUTES = env.int("PRE_EXAM_NUDGE_MINUTES", default=30)
STREAK_MILESTONES = env.list("STREAK_MILESTONES", cast=int, default=[3, 7, 14, 30, 50, 100])

UNFOLD = {
    "SITE_TITLE": "4000 Essential Words",
    "SITE_HEADER": "4000 Essential Words",
    "SITE_SYMBOL": "school",
}
