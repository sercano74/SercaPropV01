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
