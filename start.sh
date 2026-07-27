#!/bin/bash
set -e

echo "=== Ejecutando migraciones ==="
python manage.py migrate --noinput

echo "=== Recopilando estáticos ==="
python manage.py collectstatic --noinput

echo "=== Iniciando servidor ==="
exec gunicorn SercaProp.wsgi --bind 0.0.0.0:$PORT --log-file -
