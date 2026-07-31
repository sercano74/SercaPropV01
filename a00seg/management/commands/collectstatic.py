"""
Comando collectstatic estándar de Django.

`django-cloudinary-storage` registra su propio comando `collectstatic` que
sobrescribe al de Django y no copia archivos a menos que el storage estático
sea `StaticCloudinaryStorage`. Este proyecto usa Whitenoise para estáticos,
así que restauramos aquí el comportamiento estándar de Django.

Como esta app (`a00seg`) aparece DESPUÉS de `cloudinary_storage` en
INSTALLED_APPS, Django resuelve `collectstatic` a este comando.
"""
from django.contrib.staticfiles.management.commands.collectstatic import Command


__all__ = ['Command']
