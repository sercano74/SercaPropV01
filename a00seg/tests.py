"""Tests del almacenamiento de medios y de la validación de archivos subidos."""
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase

from a00seg.storage import SercaMediaStorage
from a00seg.uploads import validar_archivo_documento


class SercaMediaStorageTests(SimpleTestCase):
    """Regresión del bug: todo se subía como imagen y Cloudinary rechazaba el Word.

    Cloudinary responde "Unsupported ZIP file" cuando un .docx (que es un ZIP)
    entra por el pipeline de imágenes.
    """

    def setUp(self):
        self.storage = SercaMediaStorage()

    def test_los_documentos_se_suben_como_raw(self):
        nombres = (
            "ordenes_gestion/Orden de Gestion.docx",
            "ordenes_gestion/orden.doc",
            "docs_gestion/plantilla.xlsx",
            "docs_gestion/instructivo.pptx",
            "obs_solicitud/detalle.txt",
            "docs_legales/antecedentes.zip",
        )
        for nombre in nombres:
            with self.subTest(nombre=nombre):
                self.assertEqual(self.storage._get_resource_type(nombre), "raw")

    def test_las_imagenes_se_suben_como_image(self):
        nombres = (
            "propiedades/foto.JPG",
            "propiedades/foto.png",
            "usuarios/foto.webp",
            "comprobantes_solicitud/comprobante.gif",
        )
        for nombre in nombres:
            with self.subTest(nombre=nombre):
                self.assertEqual(self.storage._get_resource_type(nombre), "image")

    def test_los_pdf_se_siguen_subiendo_como_image(self):
        # Cloudinary sirve los PDF por el pipeline de imágenes y los archivos ya
        # guardados se subieron así: no debe cambiar.
        self.assertEqual(self.storage._get_resource_type("ordenes_gestion/OG.pdf"), "image")

    def test_public_id_antiguo_sin_extension_se_resuelve_como_image(self):
        self.assertEqual(self.storage._get_resource_type("ordenes_gestion/OG_n7wxgu"), "image")

    def test_los_videos_se_suben_como_video(self):
        self.assertEqual(self.storage._get_resource_type("propiedades/tour.mp4"), "video")

    def test_un_nombre_largo_conserva_la_extension(self):
        nombre = "ordenes_gestion/" + ("Orden de Gestion " * 12) + ".docx"
        recortado = self.storage.get_available_name(nombre, max_length=100)

        self.assertLessEqual(len(recortado), 100)
        self.assertTrue(recortado.endswith(".docx"))
        self.assertEqual(self.storage._get_resource_type(recortado), "raw")


class ValidarArchivoDocumentoTests(SimpleTestCase):
    def test_acepta_word_pdf_y_otros_documentos(self):
        nombres = (
            "Orden de Gestion.docx",
            "Orden de Gestion.doc",
            "OG.pdf",
            "planilla.xlsx",
            "antecedentes.zip",
            "escaneo.jpg",
        )
        for nombre in nombres:
            with self.subTest(nombre=nombre):
                archivo = SimpleUploadedFile(nombre, b"contenido de prueba")
                self.assertIsNone(validar_archivo_documento(archivo))

    def test_rechaza_un_ejecutable_con_un_mensaje_claro(self):
        archivo = SimpleUploadedFile("virus.exe", b"MZ")

        error = validar_archivo_documento(archivo, etiqueta="La Orden de Gestión")

        self.assertIn("La Orden de Gestión", error)
        self.assertIn("no es un formato permitido", error)
        self.assertIn(".exe", error)

    def test_rechaza_un_archivo_sin_extension(self):
        archivo = SimpleUploadedFile("orden_de_gestion", b"contenido")

        error = validar_archivo_documento(archivo)

        self.assertIn("no tiene extensión", error)

    def test_rechaza_un_archivo_demasiado_grande(self):
        archivo = SimpleUploadedFile("OG.pdf", b"x" * 2048)

        error = validar_archivo_documento(archivo, max_mb=0.001)

        self.assertIn("máximo permitido es 0.001 MB", error)

    def test_rechaza_cuando_no_llega_archivo(self):
        self.assertIn("no fue recibido", validar_archivo_documento(None))


# ======================================================================
# Panel que habilita los planes de corredor
# ======================================================================
#
# El caso que lo origina: un corredor con plan Metrópoli no podía publicar en
# representación y no había forma de habilitarlo desde la aplicación.
# ``permite_representacion`` y ``max_publicaciones_mensual`` se leían en el
# flujo de publicación pero sólo se podían cambiar desde el admin de Django.

from decimal import Decimal  # noqa: E402

from django.contrib.auth import get_user_model  # noqa: E402
from django.test import TestCase  # noqa: E402
from django.urls import reverse  # noqa: E402
from django.utils import timezone  # noqa: E402

from a00seg.models import PlanSuscripcion, SuscripcionCorredor  # noqa: E402
from a03Prop import representacion  # noqa: E402


class GestionPlanesCorredorTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        Usuario = get_user_model()
        cls.gerente = Usuario.objects.create_user(
            username="plan_ger", email="plan_ger@x.cl", password="x", rol="gerente"
        )
        cls.corredor = Usuario.objects.create_user(
            username="plan_cor", email="plan_cor@x.cl", password="x", rol="corredor"
        )
        cls.plan = PlanSuscripcion.objects.create(
            nombre="Metropoli",
            tipo="corredor",
            precio=Decimal("120000"),
            duracion_meses=12,
            permite_representacion=False,
            max_publicaciones_mensual=5,
        )
        cls.plan_vendedor = PlanSuscripcion.objects.create(
            nombre="Vendedor Base",
            tipo="vendedor",
            precio=Decimal("50000"),
            duracion_meses=6,
        )
        SuscripcionCorredor.objects.create(
            corredor=cls.corredor,
            plan=cls.plan,
            fecha_fin=timezone.now() + timezone.timedelta(days=200),
            activa=True,
        )

    def _url(self):
        return reverse("gestion_planes_corredor")

    def _entrar_como_gerente(self):
        self.client.force_login(self.gerente)

    def test_el_panel_lista_los_planes_de_corredor(self):
        self._entrar_como_gerente()

        respuesta = self.client.get(self._url())

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Metropoli")
        # Los planes de vendedor no se gestionan aquí.
        self.assertNotContains(respuesta, "Vendedor Base")

    def test_habilitar_la_representacion_desbloquea_al_corredor(self):
        """El caso real: sin esto, el corredor quedaba bloqueado sin salida."""
        self._entrar_como_gerente()
        permitido, _ = representacion.puede_representar(self.corredor)
        self.assertFalse(permitido)

        respuesta = self.client.post(self._url(), {
            "plan_id": self.plan.id,
            "permite_representacion": "1",
            "max_publicaciones_mensual": "10",
        })

        self.assertRedirects(respuesta, self._url())
        self.plan.refresh_from_db()
        self.assertTrue(self.plan.permite_representacion)
        self.assertEqual(self.plan.max_publicaciones_mensual, 10)
        # Y el corredor del plan queda efectivamente habilitado.
        permitido, mensaje = representacion.puede_representar(self.corredor)
        self.assertTrue(permitido, mensaje)

    def test_tambien_se_puede_deshabilitar(self):
        self.plan.permite_representacion = True
        self.plan.save(update_fields=["permite_representacion"])
        self._entrar_como_gerente()

        # Sin el campo en el POST, la casilla queda desmarcada.
        self.client.post(self._url(), {
            "plan_id": self.plan.id,
            "max_publicaciones_mensual": "5",
        })

        self.plan.refresh_from_db()
        self.assertFalse(self.plan.permite_representacion)

    def test_un_tope_invalido_no_se_guarda(self):
        self._entrar_como_gerente()

        respuesta = self.client.post(self._url(), {
            "plan_id": self.plan.id,
            "permite_representacion": "1",
            "max_publicaciones_mensual": "0",
        }, follow=True)

        self.assertEqual(respuesta.status_code, 200)
        self.plan.refresh_from_db()
        # Nada cambió: ni el tope ni la habilitación del mismo POST.
        self.assertEqual(self.plan.max_publicaciones_mensual, 5)
        self.assertFalse(self.plan.permite_representacion)
        self.assertContains(respuesta, "número entero de 1 o más")

    def test_un_tope_no_numerico_no_se_guarda(self):
        self._entrar_como_gerente()

        self.client.post(self._url(), {
            "plan_id": self.plan.id,
            "max_publicaciones_mensual": "muchas",
        })

        self.plan.refresh_from_db()
        self.assertEqual(self.plan.max_publicaciones_mensual, 5)

    def test_un_corredor_no_entra_al_panel(self):
        self.client.force_login(self.corredor)

        respuesta = self.client.post(self._url(), {
            "plan_id": self.plan.id,
            "permite_representacion": "1",
            "max_publicaciones_mensual": "99",
        })

        self.assertRedirects(respuesta, reverse("gestion"))
        self.plan.refresh_from_db()
        self.assertFalse(self.plan.permite_representacion)
        self.assertEqual(self.plan.max_publicaciones_mensual, 5)

    def test_no_se_puede_tocar_un_plan_de_vendedor(self):
        self._entrar_como_gerente()

        respuesta = self.client.post(self._url(), {
            "plan_id": self.plan_vendedor.id,
            "permite_representacion": "1",
            "max_publicaciones_mensual": "99",
        })

        self.assertEqual(respuesta.status_code, 404)
        self.plan_vendedor.refresh_from_db()
        self.assertFalse(self.plan_vendedor.permite_representacion)
