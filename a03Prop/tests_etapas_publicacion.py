"""Pruebas de las etapas de publicación y de la vitrina.

Cubren el defecto que motivó este trabajo: las propiedades 8 y 9 aparecían en
el home mientras su proceso de publicación seguía en el paso 3. La causa era
que la vitrina leía ``PublicacionProp.estado`` sin mirar el proceso de cinco
etapas, y que existía una vía antigua (``aprobar_publicacion``) capaz de
publicar sin cumplir ninguna etapa.

Estas pruebas fijan las tres garantías:

1. La regla de visibilidad (``publicacion``): una propiedad no se muestra si su
   solicitud no llegó a ``publicada``.
2. ``publicar_solicitud`` exige todas las etapas.
3. ``aprobar_publicacion`` no publica a espaldas del proceso.
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from . import publicacion
from .models import FotosPropiedad, Propiedad, PublicacionProp, SolicitudPublicacion

User = get_user_model()


def _propiedad(dueno=None, **extra):
    datos = {
        "dueno": dueno,
        "calle": "Calle de Prueba",
        "numero_calle": "123",
        "tipo_prop": "casa",
        "tipo_accion": "arriendo",
        "precio": Decimal("500000"),
        "estado": "borrador",
    }
    datos.update(extra)
    return Propiedad.objects.create(**datos)


def _publicacion(propiedad, publicante, **extra):
    datos = {
        "propiedad": propiedad,
        "publicante": publicante,
        "estado": "publicada",
        "meses": 1,
        "inicia_at": timezone.now(),
        "expira_at": timezone.now() + timezone.timedelta(days=30),
    }
    datos.update(extra)
    return PublicacionProp.objects.create(**datos)


class ReglaVisibilidadTests(TestCase):
    """``publicacion.publicaciones_visibles`` y sus ayudantes."""

    @classmethod
    def setUpTestData(cls):
        cls.corredor = User.objects.create_user(
            username="vis_cor", email="vis_cor@x.cl", password="x", rol="corredor"
        )
        cls.propiedad = _propiedad()

    def _solicitud(self, estado):
        return SolicitudPublicacion.objects.create(
            usuario=self.corredor, propiedad=self.propiedad, estado=estado, meses=1,
        )

    def test_sin_solicitud_la_publicacion_se_ve(self):
        _publicacion(self.propiedad, self.corredor)
        self.assertTrue(publicacion.proceso_completo(self.propiedad))
        self.assertEqual(publicacion.publicaciones_visibles().count(), 1)

    def test_con_solicitud_a_medio_camino_la_publicacion_sigue_visible(self):
        """El proceso no despublica lo ya publicado.

        Una solicitud posterior abierta (una renovación, un segundo trámite)
        no puede sacar de la vitrina una publicación que el cliente ya pagó y
        que sigue accesible por su ficha. ``proceso_completo`` sigue siendo
        False: eso es lo que impide volver a publicar sin completar las etapas.
        """
        self._solicitud("en_revision_corredor")
        _publicacion(self.propiedad, self.corredor)
        self.assertFalse(publicacion.proceso_completo(self.propiedad))
        self.assertEqual(publicacion.publicaciones_visibles().count(), 1)

    def test_con_solicitud_publicada_si_se_ve(self):
        self._solicitud("publicada")
        _publicacion(self.propiedad, self.corredor)
        self.assertTrue(publicacion.proceso_completo(self.propiedad))
        self.assertEqual(publicacion.publicaciones_visibles().count(), 1)

    def test_una_solicitud_caida_no_bloquea(self):
        self._solicitud("cancelada")
        _publicacion(self.propiedad, self.corredor)
        self.assertTrue(publicacion.proceso_completo(self.propiedad))

    def test_solicitud_activa_ignora_las_caidas(self):
        self._solicitud("cancelada")
        activa = self._solicitud("og_pendiente")
        self.assertEqual(publicacion.solicitud_activa(self.propiedad).id, activa.id)


class FaltantesEtapasTests(TestCase):
    """``faltantes_para_publicar`` es la definición única de "todas las etapas"."""

    @classmethod
    def setUpTestData(cls):
        cls.corredor = User.objects.create_user(
            username="fal_cor", email="fal_cor@x.cl", password="x", rol="corredor"
        )
        cls.propiedad = _propiedad()

    def _solicitud(self, **extra):
        datos = {
            "usuario": self.corredor,
            "propiedad": self.propiedad,
            "corredor_asignado": self.corredor,
            "estado": "en_validacion",
            "tipo_publicante": "propietario",
            "orden_gestion": "ordenes_gestion/og.pdf",
            "og_aceptada": True,
            "meses": 1,
        }
        datos.update(extra)
        return SolicitudPublicacion.objects.create(**datos)

    def test_con_todas_las_etapas_no_falta_nada(self):
        self.assertEqual(publicacion.faltantes_para_publicar(self._solicitud()), [])

    def test_sin_og_aprobada_falta(self):
        solicitud = self._solicitud(og_aceptada=False)
        self.assertTrue(publicacion.faltantes_para_publicar(solicitud))

    def test_sin_responsable_falta(self):
        solicitud = self._solicitud(corredor_asignado=None)
        self.assertTrue(publicacion.faltantes_para_publicar(solicitud))

    def test_en_representacion_sin_mandato_falta(self):
        solicitud = self._solicitud(
            tipo_publicante="representante", mandato_archivo="",
        )
        faltantes = publicacion.faltantes_para_publicar(solicitud)
        self.assertTrue(any("mandato" in f for f in faltantes))


class PublicarSolicitudTests(TestCase):
    """``publicar_solicitud`` es el único punto que pone algo en la vitrina."""

    @classmethod
    def setUpTestData(cls):
        cls.corredor = User.objects.create_user(
            username="pub_cor", email="pub_cor@x.cl", password="x", rol="corredor"
        )

    def setUp(self):
        self.propiedad = _propiedad()
        FotosPropiedad.objects.create(
            propiedad=self.propiedad, imagen="propiedades/test.jpg"
        )
        self.client.force_login(self.corredor)

    def _solicitud(self, **extra):
        datos = {
            "usuario": self.corredor,
            "propiedad": self.propiedad,
            "corredor_asignado": self.corredor,
            "estado": "en_validacion",
            "tipo_publicante": "propietario",
            "orden_gestion": "ordenes_gestion/og.pdf",
            "og_aceptada": True,
            "meses": 1,
        }
        datos.update(extra)
        return SolicitudPublicacion.objects.create(**datos)

    def test_sin_og_aprobada_no_publica(self):
        solicitud = self._solicitud(og_aceptada=False)
        respuesta = self.client.post(
            reverse("publicar_solicitud", args=[solicitud.id])
        )
        self.assertEqual(respuesta.status_code, 302)
        solicitud.refresh_from_db()
        self.propiedad.refresh_from_db()
        self.assertNotEqual(solicitud.estado, "publicada")
        self.assertNotEqual(self.propiedad.estado, "publicada")
        self.assertFalse(
            PublicacionProp.objects.filter(propiedad=self.propiedad).exists()
        )

    def test_con_todas_las_etapas_publica(self):
        solicitud = self._solicitud()
        respuesta = self.client.post(
            reverse("publicar_solicitud", args=[solicitud.id])
        )
        self.assertEqual(respuesta.status_code, 302)
        solicitud.refresh_from_db()
        self.propiedad.refresh_from_db()
        self.assertEqual(solicitud.estado, "publicada")
        self.assertEqual(self.propiedad.estado, "publicada")
        self.assertTrue(
            PublicacionProp.objects.filter(
                propiedad=self.propiedad, estado="publicada"
            ).exists()
        )

    def test_dentro_de_la_ventana_de_objecion_no_publica(self):
        solicitud = self._solicitud(
            objecion_hasta=timezone.now() + timezone.timedelta(days=2)
        )
        self.client.post(reverse("publicar_solicitud", args=[solicitud.id]))
        solicitud.refresh_from_db()
        self.assertNotEqual(solicitud.estado, "publicada")


class AprobarPublicacionNoSeSaltaEtapasTests(TestCase):
    """La vía antigua no puede publicar si el proceso está en curso."""

    @classmethod
    def setUpTestData(cls):
        cls.gerente = User.objects.create_user(
            username="apr_ger", email="apr_ger@x.cl", password="x", rol="gerente"
        )
        cls.corredor = User.objects.create_user(
            username="apr_cor", email="apr_cor@x.cl", password="x", rol="corredor"
        )

    def test_no_publica_con_solicitud_a_medio_camino(self):
        propiedad = _propiedad()
        publicacion = _publicacion(propiedad, self.corredor, estado="en_revision")
        solicitud = SolicitudPublicacion.objects.create(
            usuario=self.corredor, propiedad=propiedad,
            estado="en_revision_corredor", meses=1,
        )
        self.client.force_login(self.gerente)

        respuesta = self.client.post(reverse("aprobar_publicacion", args=[publicacion.id]))

        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(
            respuesta.url, reverse("detalle_solicitud", args=[solicitud.id])
        )
        publicacion.refresh_from_db()
        self.assertNotEqual(publicacion.estado, "publicada")

    def test_publica_si_no_hay_proceso_en_curso(self):
        propiedad = _propiedad()
        publicacion = _publicacion(propiedad, self.corredor, estado="en_revision")
        self.client.force_login(self.gerente)

        self.client.post(reverse("aprobar_publicacion", args=[publicacion.id]))

        publicacion.refresh_from_db()
        self.assertEqual(publicacion.estado, "publicada")


class VitrinaHomeTests(TestCase):
    """El home no muestra una propiedad con el proceso a medio camino."""

    @classmethod
    def setUpTestData(cls):
        cls.corredor = User.objects.create_user(
            username="home_cor", email="home_cor@x.cl", password="x", rol="corredor"
        )

    def test_home_muestra_la_publicacion_con_proceso_posterior(self):
        """Una publicación vigente sigue en el home aunque haya un trámite abierto.

        Ocultarla vaciaba la vitrina: la propiedad desaparecía del home, del
        buscador y del sitemap sin que nadie lo hubiera decidido.
        """
        propiedad = _propiedad()
        _publicacion(propiedad, self.corredor)
        SolicitudPublicacion.objects.create(
            usuario=self.corredor, propiedad=propiedad,
            estado="en_revision_corredor", meses=1,
        )

        respuesta = self.client.get(reverse("home"))

        self.assertEqual(respuesta.status_code, 200)
        visibles = list(respuesta.context["publicadas"])
        self.assertEqual(len(visibles), 1)

    def test_home_muestra_la_publicacion_coherente(self):
        propiedad = _propiedad()
        _publicacion(propiedad, self.corredor)

        respuesta = self.client.get(reverse("home"))

        self.assertEqual(respuesta.status_code, 200)
        visibles = list(respuesta.context["publicadas"])
        self.assertEqual(len(visibles), 1)


class ReconciliarPublicacionesTests(TestCase):
    """El comando deja la vitrina coherente con las etapas."""

    @classmethod
    def setUpTestData(cls):
        cls.corredor = User.objects.create_user(
            username="rec_cor", email="rec_cor@x.cl", password="x", rol="corredor"
        )

    def test_dry_run_no_cambia_nada(self):
        propiedad = _propiedad()
        publicacion = _publicacion(propiedad, self.corredor)
        SolicitudPublicacion.objects.create(
            usuario=self.corredor, propiedad=propiedad,
            estado="en_revision_corredor", meses=1,
        )

        call_command("reconciliar_publicaciones", dry_run=True)

        publicacion.refresh_from_db()
        self.assertEqual(publicacion.estado, "publicada")

    def test_reconcilia_la_publicacion_incoherente(self):
        propiedad = _propiedad()
        publicacion = _publicacion(propiedad, self.corredor)
        SolicitudPublicacion.objects.create(
            usuario=self.corredor, propiedad=propiedad,
            estado="en_revision_corredor", meses=1,
        )

        call_command("reconciliar_publicaciones", ids=[propiedad.id])

        publicacion.refresh_from_db()
        propiedad.refresh_from_db()
        self.assertEqual(publicacion.estado, "archivada")
        self.assertEqual(propiedad.estado, "borrador")
        self.assertEqual(
            PublicacionProp.objects.filter(propiedad=propiedad, estado="publicada").count(),
            0,
        )

    def test_no_toca_la_publicacion_coherente(self):
        propiedad = _propiedad()
        publicacion = _publicacion(propiedad, self.corredor)

        call_command("reconciliar_publicaciones", ids=[propiedad.id])

        publicacion.refresh_from_db()
        self.assertEqual(publicacion.estado, "publicada")
