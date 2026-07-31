#!/bin/bash
set -e
echo "=== Migrando base de datos ==="
python manage.py migrate --noinput
echo "=== Poblando regiones y comunas ==="
python scripts/poblar_regiones_comunas.py
echo "=== Colectando estáticos ==="
python manage.py collectstatic --noinput --clear
echo "=== Iniciando servidor ==="
exec gunicorn SercaProp.wsgi --bind 0.0.0.0:$PORT --log-file -
