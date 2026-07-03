#!/usr/bin/env bash
set -e

if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
  python manage.py migrate --noinput
fi
if [ "${COLLECT_STATIC:-0}" = "1" ]; then
  python manage.py collectstatic --noinput
fi

exec "$@"
