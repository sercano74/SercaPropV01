"""
Management command para migrar todas las imágenes locales a Cloudinary.

USO:
    python manage.py migrate_to_cloudinary

Requiere CLOUDINARY_URL configurada en Railway (ya lo está).
"""
import logging
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Migra todas las imágenes de storage local a Cloudinary'

    def handle(self, *args, **options):
        from a03Prop.models import FotosPropiedad, SolicitudPublicacion, PublicacionProp, LegalDocsProp
        from a00seg.models import User

        self._migrar_fotos_propiedad()
        self._migrar_fotos_perfil()
        self._migrar_comprobantes()
        self._migrar_docs_legales()
        self.stdout.write(self.style.SUCCESS("✅ Migración completada"))

    def _subir(self, instancia, field_name):
        """Fuerza re-subida de un archivo a Cloudinary si está en local."""
        field = getattr(instancia, field_name)
        if not field or not field.name:
            return False
        try:
            url = field.url
            if 'cloudinary' in url or 'res.cloudinary.com' in url:
                self.stdout.write(f"  ⏭️  Ya en Cloudinary: {field.name}")
                return False
            with field.open('rb') as f:
                data = f.read()
            if not data:
                return False
            nuevo = ContentFile(data, name=field.name)
            nuevo_path = default_storage.save(field.name, nuevo)
            setattr(instancia, field_name, nuevo_path)
            instancia.save(update_fields=[field_name])
            self.stdout.write(f"  ✅ {field.name}")
            return True
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"  ❌ {field.name}: {e}"))
            return False

    def _migrar_fotos_propiedad(self):
        from a03Prop.models import FotosPropiedad
        self.stdout.write("\n📸 FotosPropiedad...")
        total = FotosPropiedad.objects.count()
        ok = sum(1 for f in FotosPropiedad.objects.iterator() if self._subir(f, 'imagen'))
        self.stdout.write(self.style.SUCCESS(f"  {ok}/{total}"))

    def _migrar_fotos_perfil(self):
        self.stdout.write("\n👤 Fotos perfil...")
        qs = User.objects.exclude(foto='')
        total = qs.count()
        ok = sum(1 for u in qs.iterator() if self._subir(u, 'foto'))
        self.stdout.write(self.style.SUCCESS(f"  {ok}/{total}"))

    def _migrar_comprobantes(self):
        self.stdout.write("\n📄 Comprobantes...")
        ok = 0
        for qs in [SolicitudPublicacion.objects.exclude(comprobante=''),
                   PublicacionProp.objects.exclude(comprobante='')]:
            ok += sum(1 for i in qs.iterator() if self._subir(i, 'comprobante'))
        self.stdout.write(self.style.SUCCESS(f"  {ok} migrados"))

    def _migrar_docs_legales(self):
        self.stdout.write("\n📑 Docs legales...")
        qs = LegalDocsProp.objects.exclude(documento='')
        total = qs.count()
        ok = sum(1 for d in qs.iterator() if self._subir(d, 'documento'))
        self.stdout.write(self.style.SUCCESS(f"  {ok}/{total}"))
