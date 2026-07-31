# -*- coding: utf-8 -*-
"""
Corrige servicios que quedaron con la imagen placeholder rota (404):
Estos campos 'imagen' que apuntan a rutas sin archivo real se dejan vacíos,
de modo que los templates muestren el emoji 🔧 hasta que el prestador suba
una imagen real desde su panel "Mis servicios".

Ejecutar: python scripts/arreglar_imagen_servicios.py
"""
import django, os, sys
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'SercaProp.settings')
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
django.setup()

from django.core.files.storage import default_storage
from a07serv.models import ServicioPublicitario

PLACEHOLDER = "servicios/placeholder.jpg"

arreglados = 0
for s in ServicioPublicitario.objects.exclude(imagen="").iterator():
    name = s.imagen.name
    # Solo los que apuntan al placeholder inexistente o a rutas sin archivo real
    if name == PLACEHOLDER or (not name.startswith("http") and not default_storage.exists(name)):
        previo = name
        s.imagen = None
        s.save(update_fields=["imagen", "updated_at"])
        arreglados += 1
        print(f"OK Servicio #{s.id} '{s.titulo}': imagen '{previo}' -> vacía (mostrará emoji hasta subir imagen real)")
    else:
        print(f"- Servicio #{s.id} '{s.titulo}': imagen '{name}' sin cambios")

print(f"\nTotal corregidos: {arreglados}")
