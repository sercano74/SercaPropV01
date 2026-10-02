"""Tests del paso 3 del flujo de publicación: el corredor sube la Orden de Gestión.

Cubre el bug reportado: subir la OG en Word devolvía la página 500 porque el
archivo entraba al pipeline de imágenes de Cloudinary ("Unsupported ZIP file").
Los archivos se guardan en un almacenamiento local temporal para que las pruebas
no dependan de la red.
"""
import atexit
import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from a00seg.models import User
from a01Com.models import Communication
from a03Prop.models import SolicitudPublicacion

MEDIA_TEMPORAL = tempfile.mkdtemp(prefix="serca_og_test_")
atexit.register(shutil.rmtree, MEDIA_TEMPORAL, True)

ALMACENAMIENTO_LOCAL = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

CONTENT_TYPE_WORD = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def archivo_word(nombre="Orden de Gestion.docx"):
    return SimpleUploadedFile(nombre, b"contenido de la orden de gestion", content_type=CONTENT_TYPE_WORD)


@override_settings(STORAGES=ALMACENAMIENTO_LOCAL, MEDIA_ROOT=MEDIA_TEMPORAL)
class SubirOrdenGestionTests(TestCase):
    """El corredor asignado debe poder subir la OG en Word, no solo en PDF."""

    def setUp(self):
        self.corredor = User.objects.create_user(
            username="corredor_og",
            email="corredor_og@example.com",
            password="clave",
            rol="corredor",
        )
        self.usuario = User.objects.create_user(
            username="usuario_og",
            email="usuario_og@example.com",
            password="clave",
            rol="base",
        )
        self.solicitud = SolicitudPublicacion.objects.create(
            usuario=self.usuario,
            corredor_asignado=self.corredor,
            estado="en_revision_corredor",
        )
        self.url = reverse("subir_orden_gestion", args=[self.solicitud.id])

    def test_subir_la_og_en_word_guarda_el_archivo(self):
        self.client.force_login(self.corredor)

        respuesta = self.client.post(
            self.url,
            {"orden_gestion": archivo_word(), "docs_requeridos": "Dominio vigente"},
            follow=True,
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Orden de Gestión subida")

        self.solicitud.refresh_from_db()
        self.assertEqual(self.solicitud.estado, "og_pendiente")
        self.assertEqual(self.solicitud.docs_requeridos, "Dominio vigente")
        self.assertTrue(self.solicitud.orden_gestion.name.endswith(".docx"))
        self.assertTrue(
            self.solicitud.orden_gestion.storage.exists(self.solicitud.orden_gestion.name)
        )
        self.assertTrue(
            Communication.objects.filter(recipient=self.usuario, title__icontains="Orden").exists()
        )

    def test_subir_la_og_en_pdf_sigue_funcionando(self):
        self.client.force_login(self.corredor)

        respuesta = self.client.post(
            self.url,
            {
                "orden_gestion": SimpleUploadedFile(
                    "OG.pdf", b"%PDF-1.4 contenido", content_type="application/pdf"
                )
            },
            follow=True,
        )

        self.assertEqual(respuesta.status_code, 200)

        self.solicitud.refresh_from_db()
        self.assertEqual(self.solicitud.estado, "og_pendiente")
        self.assertTrue(self.solicitud.orden_gestion.name.endswith(".pdf"))

    def test_un_formato_no_permitido_muestra_error_y_no_guarda_nada(self):
        self.client.force_login(self.corredor)

        respuesta = self.client.post(
            self.url,
            {
                "orden_gestion": SimpleUploadedFile(
                    "virus.exe", b"MZ", content_type="application/octet-stream"
                )
            },
            follow=True,
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "no es un formato permitido")

        self.solicitud.refresh_from_db()
        self.assertEqual(self.solicitud.estado, "en_revision_corredor")
        self.assertFalse(self.solicitud.orden_gestion)
        self.assertFalse(Communication.objects.exists())

    def test_solo_el_corredor_asignado_puede_subir_la_og(self):
        otro_corredor = User.objects.create_user(
            username="otro_corredor",
            email="otro_corredor@example.com",
            password="clave",
            rol="corredor",
        )
        self.client.force_login(otro_corredor)

        self.client.post(self.url, {"orden_gestion": archivo_word()})

        self.solicitud.refresh_from_db()
        self.assertEqual(self.solicitud.estado, "en_revision_corredor")
        self.assertFalse(self.solicitud.orden_gestion)
