# -*- coding: utf-8 -*-
"""
Sube las imágenes locales de media/servicios/ a Cloudinary bajo sus rutas
originales (servicios/<nombre>), de modo que las URLs que ya están guardadas
en la base de datos (producción) funcionen de inmediato.

Ejecutar: python scripts/subir_imagenes_servicios_cloudinary.py
"""
import django, os, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'SercaProp.settings')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
django.setup()

from pathlib import Path
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from a07serv.models import ServicioPublicitario

MEDIA_SERVICIOS = Path(__file__).resolve().parent.parent / "media" / "servicios"

if not MEDIA_SERVICIOS.exists():
    print(f"No existe la carpeta {MEDIA_SERVICIOS}")
    sys.exit(1)

subidos = 0
for archivo in sorted(MEDIA_SERVICIOS.iterdir()):
    if not archivo.is_file():
        continue
    nombre = archivo.name
    ruta_storage = f"servicios/{nombre}"

    if default_storage.exists(ruta_storage):
        print(f"⏭️  Ya existe en storage: {ruta_storage}")
        continue

    try:
        with open(archivo, "rb") as f:
            data = f.read()
        if not data:
            print(f"❌ {nombre}: archivo vacío")
            continue
        nuevo = ContentFile(data, name=ruta_storage)
        guardado = default_storage.save(ruta_storage, nuevo)
        subidos += 1
        print(f"✅ Subido: {guardado}")
    except Exception as e:
        print(f"❌ {nombre}: {e}")

print(f"\nSubidos: {subidos}. Total servicios con imagen en BD local:")
for s in ServicioPublicitario.objects.all():
    print(f"  #{s.id} '{s.titulo}': imagen={s.imagen.name if s.imagen else 'VACÍA'}")
