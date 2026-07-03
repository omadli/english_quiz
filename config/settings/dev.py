from .base import *  # noqa: F403

DEBUG = True
ALLOWED_HOSTS = ["*"]

# Manifest static storage requires `collectstatic` to have run (it needs the
# hashed-filename manifest). That's a production concern; for local dev/test
# runs (incl. pytest driving the admin through the test client) use plain
# compressed storage so {% static %} works without a build step.
STORAGES = {
    **STORAGES,  # noqa: F405
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
}
