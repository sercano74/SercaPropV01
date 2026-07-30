"""
Script de migración de imágenes locales a Cloudinary.

USO:
    python manage.py migrate_to_cloudinary

Requiere:
    - CLOUDINARY_URL configurada (en Railway ya lo está)
    - django-cloudinary-storage >= 0.3.0
    - cloudinary >= 1.41.0

Este script:
    1. Escanea todas las FotosPropiedad que aún están en storage local
    2. Las re-subirá a Cloudinary forzando la subida
    3. Actualiza las URLs en BD

Ejecutar en Railway desde Console: python manage.py migrate_to_cloudinary
"""
import os
import io
import logging
from pathlib import Path

from django.core.files.base import ContentFile, File
from django.core.files.storage import default_storage
from django.conf import settings
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Migra todas las imágenes de storage local a Cloudinary'

    def handle(self, *args, **options):
        from a03Prop.models import FotosPropiedad
        from a00seg.models import User

        # 1) FotosPropiedad
        self._migrar_fotos_propiedad()

        # 2) Fotos de perfil de usuario
        self._migrar_fotos_perfil()

        # 3) Comprobantes de solicitud
        self._migrar_comprobantes_solicitud()

        # 4) Documentos legales
        self._migrar_docs_legales()

        self.stdout.write(self.style.SUCCESS("✅ Migración completada"))

    def _subir_a_cloudinary(self, instancia, field_name, model_name):
        """Fuerza la re-subida de un archivo a Cloudinary."""
        field = getattr(instancia, field_name)
        if not field or not field.name:
            return False

        try:
            # Verificar si ya está en Cloudinary
            url_actual = field.url
            if 'cloudinary' in url_actual or 'res.cloudinary.com' in url_actual:
                self.stdout.write(f"  ⏭️  Ya en Cloudinary: {field.name}")
                return True

            # Leer el archivo actual
            try:
                with field.open('rb') as f:
                    contenido = f.read()
            except Exception as e:
                self.stdout.write(self.style.WARNING(
                    f"  ⚠️  No se pudo leer {field.name}: {e}"
                ))
                return False

            if not contenido:
                self.stdout.write(self.style.WARNING(
                    f"  ⚠️  Archivo vacío: {field.name}"
                ))
                return False

            # Guardar forzando Cloudinary (el default_storage ya apunta a Cloudinary)
            nombre_archivo = field.name
            nuevo_file = ContentFile(contenido, name=nombre_archivo)
            nuevo_path = default_storage.save(nombre_archivo, nuevo_file)

            # Actualizar el campo con el nuevo path
            setattr(instancia, field_name, nuevo_path)
            instancia.save(update_fields=[field_name])

            self.stdout.write(f"  ✅ Migrado: {nombre_archivo}")
            return True

        except Exception as e:
            self.stdout.write(self.style.ERROR(
                f"  ❌ Error migrando {field.name}: {e}"
            ))
            return False

    def _migrar_fotos_propiedad(self):
        from a03Prop.models import FotosPropiedad
        self.stdout.write("\n📸 Migrando FotosPropiedad...")
        total = FotosPropiedad.objects.count()
        ok = 0
        for i, foto in enumerate(FotosPropiedad.objects.iterator()):
            if self._subir_a_cloudinary(foto, 'imagen', 'FotosPropiedad'):
                ok += 1
            if (i + 1) % 10 == 0:
                self.stdout.write(f"  Progreso: {i+1}/{total}")
        self.stdout.write(self.style.SUCCESS(f"  Fotos: {ok}/{total} migradas"))

    def _migrar_fotos_perfil(self):
        from a00seg.models import User
        self.stdout.write("\n👤 Migrando fotos de perfil...")
        total = User.objects.exclude(foto='').count()
        ok = 0
        for user in User.objects.exclude(foto='').iterator():
            if self._subir_a_cloudinary(user, 'foto', 'User'):
                ok += 1
        self.stdout.write(self.style.SUCCESS(f"  Fotos perfil: {ok}/{total} migradas"))

    def _migrar_comprobantes_solicitud(self):
        from a03Prop.models import SolicitudPublicacion, PublicacionProp
        self.stdout.write("\n📄 Migrando comprobantes...")
        modelos = [
            (SolicitudPublicacion.objects.exclude(comprobante=''), 'comprobante'),
            (PublicacionProp.objects.exclude(comprobante=''), 'comprobante'),
        ]
        total = sum(m.count() for m, _ in modelos)
        ok = 0
        for qs, field in modelos:
            for inst in qs.iterator():
                if self._subir_a_cloudinary(inst, field, 'Comprobante'):
                    ok += 1
        self.stdout.write(self.style.SUCCESS(f"  Comprobantes: {ok}/{total} migrados"))

    def _migrar_docs_legales(self):
        from a03Prop.models import LegalDocsProp
        self.stdout.write("\n📑 Migrando documentos legales...")
        total = LegalDocsProp.objects.exclude(documento='').count()
        ok = 0
        for doc in LegalDocsProp.objects.exclude(documento='').iterator():
            if self._subir_a_cloudinary(doc, 'documento', 'LegalDocsProp'):
                ok += 1
        self.stdout.write(self.style.SUCCESS(f"  Docs legales: {ok}/{total} migrados"))
