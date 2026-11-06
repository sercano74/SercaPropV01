"""Tests del flujo de publicación en representación, comisiones y acciones.

Cubren las tres piezas donde vive la lógica que no se ve en pantalla:

- ``comisiones``: conversión a CLP y fiscalización por rol.
- ``orden_gestion``: lectura de las condiciones de la OG.
- ``acciones_de``: la máquina de estados de la interfaz, que es donde se
  atascaba el flujo cuando un usuario tenía dos roles.
"""

import tempfile
from decimal import Decimal
from types import SimpleNamespace

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from a00seg.models import PlanSuscripcion, SuscripcionCorredor
from a01Com.models import Communication

from . import comisiones, orden_gestion, representacion
from .models import CorredorProp, Propiedad, PublicacionProp, SolicitudPublicacion

User = get_user_model()


def _crear_propiedad(dueno, **extra):
    datos = {
        "dueno": dueno,
        "calle": "Calle de Prueba",
        "numero_calle": "123",
        "tipo_prop": "casa",
        "tipo_accion": "venta",
        "precio": Decimal("100000000"),
    }
    datos.update(extra)
    return Propiedad.objects.create(**datos)


# ======================================================================
# comisiones: conversión y fiscalización
# ======================================================================

class ADecimalTests(SimpleTestCase):
    def test_acepta_texto_y_decimal(self):
        self.assertEqual(comisiones._a_decimal("1500.50"), Decimal("1500.50"))
        self.assertEqual(comisiones._a_decimal(Decimal("2")), Decimal("2"))

    def test_devuelve_none_con_basura(self):
        for basura in (None, "", "abc", "12,5"):
            self.assertIsNone(comisiones._a_decimal(basura), basura)


class ConversionAClpTests(SimpleTestCase):
    def test_clp_no_necesita_factor(self):
        self.assertEqual(
            comisiones.convertir_a_clp(Decimal("1000000"), "PCL"),
            Decimal("1000000.00"),
        )

    def test_uf_multiplica_por_el_factor(self):
        self.assertEqual(
            comisiones.convertir_a_clp(Decimal("1000"), "UF", factor_uf="38500"),
            Decimal("38500000.00"),
        )

    def test_usd_multiplica_por_el_factor(self):
        self.assertEqual(
            comisiones.convertir_a_clp(Decimal("100"), "USD", factor_usd="950"),
            Decimal("95000.00"),
        )

    def test_sin_factor_devuelve_none_y_no_cero(self):
        self.assertIsNone(comisiones.convertir_a_clp(Decimal("10"), "UF"))
        self.assertIsNone(comisiones.convertir_a_clp(Decimal("10"), "USD"))

    def test_normalizar_moneda_acepta_clp_y_descarta_lo_desconocido(self):
        self.assertEqual(comisiones.normalizar_moneda("CLP"), "PCL")
        self.assertEqual(comisiones.normalizar_moneda("uf"), "UF")
        self.assertEqual(comisiones.normalizar_moneda("EUR"), "PCL")


class ComisionTests(SimpleTestCase):
    def test_porcentaje_sobre_la_base(self):
        self.assertEqual(
            comisiones.calcular_comision_clp(
                base_clp=Decimal("100000000"), tipo="porcentaje", valor="2"
            ),
            Decimal("2000000.00"),
        )

    def test_monto_fijo_en_pesos_ignora_la_base(self):
        self.assertEqual(
            comisiones.calcular_comision_clp(
                base_clp=Decimal("100000000"), tipo="fijo", valor="1500000"
            ),
            Decimal("1500000.00"),
        )

    def test_monto_fijo_en_uf_se_convierte_con_el_factor(self):
        self.assertEqual(
            comisiones.calcular_comision_clp(
                base_clp=Decimal("1"), tipo="fijo", valor="10",
                moneda="UF", factor_uf="38500",
            ),
            Decimal("385000.00"),
        )

    def test_fijo_en_uf_sin_factor_devuelve_none(self):
        self.assertIsNone(
            comisiones.calcular_comision_clp(
                base_clp=Decimal("1"), tipo="fijo", valor="10", moneda="UF"
            )
        )

    def test_sin_valor_no_hay_comision(self):
        self.assertIsNone(
            comisiones.calcular_comision_clp(
                base_clp=Decimal("1000"), tipo="porcentaje", valor=None
            )
        )

    def test_normalizar_tipo_cae_en_porcentaje(self):
        self.assertEqual(comisiones.normalizar_tipo("FIJO"), "fijo")
        self.assertEqual(comisiones.normalizar_tipo("cualquiera"), "porcentaje")


class FiscalizacionTests(SimpleTestCase):
    def test_la_gerencia_no_se_fiscaliza(self):
        self.assertFalse(comisiones.aplica_fiscalizacion("gerente"))
        self.assertFalse(comisiones.aplica_fiscalizacion("superadmin"))

    def test_los_demas_roles_si(self):
        for rol in ("corredor", "base", ""):
            self.assertTrue(comisiones.aplica_fiscalizacion(rol), rol)

    def test_desviacion_no_inventa_cero_sin_datos(self):
        self.assertIsNone(comisiones.desviacion_tasa(None, Decimal("70")))
        self.assertIsNone(comisiones.desviacion_tasa(Decimal("70"), None))
        self.assertEqual(
            comisiones.desviacion_tasa(Decimal("70"), Decimal("65")),
            Decimal("-5.00"),
        )

    def test_rangos(self):
        self.assertEqual(comisiones.validar_rangos(tipo="porcentaje", valor="2"), [])
        self.assertTrue(comisiones.validar_rangos(tipo="porcentaje", valor="150"))
        self.assertTrue(comisiones.validar_rangos(tipo="fijo", valor="-1"))
        self.assertTrue(
            comisiones.validar_rangos(tipo="porcentaje", valor="2", tasa_serca="120")
        )


# ======================================================================
# orden_gestion: condiciones de la OG
# ======================================================================

class CondicionesOgTests(SimpleTestCase):
    CORREDOR = SimpleNamespace(rol="corredor")
    GERENTE = SimpleNamespace(rol="gerente")

    def _post(self, **extra):
        base = {
            "precio_referencia_og": "500000000",
            "moneda_referencia_og": "PCL",
            "tasa_serca_og": "30",
            "tipo_comision_vendedor_og": "porcentaje",
            "valor_comision_vendedor_og": "2",
            "moneda_comision_vendedor_og": "PCL",
            "tipo_comision_comprador_og": "porcentaje",
            "valor_comision_comprador_og": "1",
            "moneda_comision_comprador_og": "PCL",
        }
        base.update(extra)
        return base

    def test_condiciones_completas_no_dan_error(self):
        datos, errores, _ = orden_gestion.parsear_condiciones(
            self._post(), user=self.CORREDOR
        )
        self.assertEqual(errores, [])
        self.assertEqual(datos["precio_referencia_og"], Decimal("500000000"))

    def test_falta_el_precio_de_referencia(self):
        _, errores, _ = orden_gestion.parsear_condiciones(
            self._post(precio_referencia_og=""), user=self.GERENTE
        )
        self.assertTrue(any("precio de referencia" in e.lower() for e in errores))

    def test_falta_la_tasa_serca(self):
        _, errores, _ = orden_gestion.parsear_condiciones(
            self._post(tasa_serca_og=""), user=self.GERENTE
        )
        self.assertTrue(any("tasa serca" in e.lower() for e in errores))

    def test_uf_sin_factor_es_error(self):
        _, errores, _ = orden_gestion.parsear_condiciones(
            self._post(moneda_referencia_og="UF"), user=self.GERENTE
        )
        self.assertTrue(any("uf" in e.lower() for e in errores))

    def test_uf_con_factor_y_fecha_pasa(self):
        _, errores, _ = orden_gestion.parsear_condiciones(
            self._post(
                moneda_referencia_og="UF",
                factor_uf_og="38500",
                fecha_tipo_cambio_og="2026-03-01",
            ),
            user=self.GERENTE,
        )
        self.assertEqual(errores, [])

    def test_al_corredor_se_le_avisa_la_desviacion_de_la_tasa(self):
        _, errores, advertencias = orden_gestion.parsear_condiciones(
            self._post(tasa_serca_og="25"), user=self.CORREDOR,
            tasa_plan=Decimal("30"),
        )
        self.assertEqual(errores, [])
        self.assertTrue(advertencias)
        self.assertTrue(any("tasa" in a.lower() for a in advertencias))

    def test_a_la_gerencia_no_se_le_avisa_nada(self):
        _, errores, advertencias = orden_gestion.parsear_condiciones(
            self._post(tasa_serca_og="25"), user=self.GERENTE,
            tasa_plan=Decimal("30"),
        )
        self.assertEqual(errores, [])
        self.assertEqual(advertencias, [])

    def test_sin_desviacion_no_hay_aviso(self):
        _, _, advertencias = orden_gestion.parsear_condiciones(
            self._post(tasa_serca_og="30"), user=self.CORREDOR,
            tasa_plan=Decimal("30"),
        )
        self.assertEqual(advertencias, [])


class ValoresInicialesCierreTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.dueno = User.objects.create_user(
            username="dueno_cierre", email="dueno@x.cl", password="x", rol="base"
        )
        cls.corredor = User.objects.create_user(
            username="cor_cierre", email="cor@x.cl", password="x", rol="corredor"
        )

    def test_sin_og_ni_corredor_no_inventa_valores(self):
        propiedad = _crear_propiedad(self.dueno, precio=Decimal("50000000"))
        datos = orden_gestion.valores_iniciales_para_cierre(propiedad)
        self.assertEqual(datos["origen_comisiones"], "")
        self.assertIsNone(datos["valor_comision_vendedor_origen"])

    def test_sin_og_cae_en_la_ficha_del_corredor(self):
        propiedad = _crear_propiedad(self.dueno)
        CorredorProp.objects.create(
            propiedad=propiedad, corredor=self.corredor, estado="activa",
            tipo_comision="fijo", monto_comision_dueno=Decimal("1500000"),
            monto_comision_usu=Decimal("500000"),
        )
        datos = orden_gestion.valores_iniciales_para_cierre(propiedad)
        self.assertEqual(datos["origen_comisiones"], comisiones.ORIGEN_CORREDOR_PROP)
        self.assertEqual(datos["tipo_comision_vendedor"], "fijo")
        self.assertEqual(
            datos["valor_comision_vendedor_origen"], Decimal("1500000.00")
        )

    def test_con_og_manda_la_og(self):
        propiedad = _crear_propiedad(self.dueno)
        CorredorProp.objects.create(
            propiedad=propiedad, corredor=self.corredor, estado="activa",
            tipo_comision="porcentaje", monto_comision_dueno=Decimal("9"),
            monto_comision_usu=Decimal("9"),
        )
        SolicitudPublicacion.objects.create(
            usuario=self.corredor, propiedad=propiedad, estado="og_aceptada",
            precio_referencia_og=Decimal("100000000"),
            moneda_referencia_og="PCL",
            tasa_serca_og=Decimal("30"),
            tipo_comision_vendedor_og="porcentaje",
            valor_comision_vendedor_og=Decimal("2"),
            moneda_comision_vendedor_og="PCL",
        )
        datos = orden_gestion.valores_iniciales_para_cierre(propiedad)
        self.assertEqual(datos["origen_comisiones"], comisiones.ORIGEN_OG)
        self.assertEqual(datos["valor_comision_vendedor_origen"], Decimal("2.00"))
        self.assertEqual(datos["precio_referencia"], Decimal("100000000.00"))


# ======================================================================
# representacion: permisos, cupo y datos del propietario
# ======================================================================

class PuedeRepresentarTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.corredor = User.objects.create_user(
            username="rep_cor", email="rep_cor@x.cl", password="x", rol="corredor"
        )
        cls.gerente = User.objects.create_user(
            username="rep_ger", email="rep_ger@x.cl", password="x", rol="gerente"
        )
        cls.plan_sin = PlanSuscripcion.objects.create(
            nombre="Basico", tipo="corredor", precio=Decimal("10000"),
            duracion_meses=1, permite_representacion=False,
            max_publicaciones_mensual=3,
        )
        cls.plan_con = PlanSuscripcion.objects.create(
            nombre="Prime", tipo="corredor", precio=Decimal("20000"),
            duracion_meses=1, permite_representacion=True,
            max_publicaciones_mensual=10,
        )

    def _suscribir(self, user, plan, dias=30):
        SuscripcionCorredor.objects.update_or_create(
            corredor=user,
            defaults={
                "plan": plan,
                "fecha_fin": timezone.now() + timezone.timedelta(days=dias),
                "activa": True,
            },
        )

    def test_sin_suscripcion_no_puede(self):
        permitido, mensaje = representacion.puede_representar(self.corredor)
        self.assertFalse(permitido)
        self.assertTrue(mensaje)

    def test_plan_sin_permiso_no_puede(self):
        self._suscribir(self.corredor, self.plan_sin)
        permitido, mensaje = representacion.puede_representar(self.corredor)
        self.assertFalse(permitido)
        self.assertIn("Basico", mensaje)
        # El motivo dice qué hacer y quién puede hacerlo: no basta con
        # informar el bloqueo, hay que dejar salida.
        self.assertIn("Planes de corredor", mensaje)

    def test_plan_con_permiso_puede(self):
        self._suscribir(self.corredor, self.plan_con)
        permitido, mensaje = representacion.puede_representar(self.corredor)
        self.assertTrue(permitido, mensaje)

    def test_suscripcion_vencida_no_sirve(self):
        self._suscribir(self.corredor, self.plan_con, dias=-1)
        permitido, _ = representacion.puede_representar(self.corredor)
        self.assertFalse(permitido)

    def test_la_gerencia_siempre_puede(self):
        permitido, mensaje = representacion.puede_representar(self.gerente)
        self.assertTrue(permitido, mensaje)


class CupoMensualTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.corredor = User.objects.create_user(
            username="cupo_cor", email="cupo_cor@x.cl", password="x", rol="corredor"
        )
        cls.gerente = User.objects.create_user(
            username="cupo_ger", email="cupo_ger@x.cl", password="x", rol="gerente"
        )
        cls.plan = PlanSuscripcion.objects.create(
            nombre="Prime", tipo="corredor", precio=Decimal("20000"),
            duracion_meses=1, permite_representacion=True,
            max_publicaciones_mensual=2,
        )
        SuscripcionCorredor.objects.create(
            corredor=cls.corredor, plan=cls.plan,
            fecha_fin=timezone.now() + timezone.timedelta(days=30),
            activa=True,
        )
        cls.propiedad = _crear_propiedad(cls.corredor)

    def test_cupo_inicial(self):
        usadas, limite = representacion.cupo_del_mes(self.corredor)
        self.assertEqual(usadas, 0)
        self.assertEqual(limite, 2)

    def test_la_gerencia_no_tiene_tope(self):
        usadas, limite = representacion.cupo_del_mes(self.gerente)
        self.assertEqual(usadas, 0)
        self.assertIsNone(limite)

    def test_cuenta_las_publicaciones_del_mes(self):
        SolicitudPublicacion.objects.create(
            usuario=self.corredor, propiedad=self.propiedad, estado="pago_revision",
        )
        usadas, _ = representacion.cupo_del_mes(self.corredor)
        self.assertEqual(usadas, 1)

    def test_las_caidas_no_consumen_cupo(self):
        SolicitudPublicacion.objects.create(
            usuario=self.corredor, propiedad=self.propiedad, estado="cancelada",
        )
        usadas, _ = representacion.cupo_del_mes(self.corredor)
        self.assertEqual(usadas, 0)

    def test_cupo_agotado_bloquea(self):
        for _ in range(2):
            SolicitudPublicacion.objects.create(
                usuario=self.corredor, propiedad=self.propiedad,
                estado="pago_revision",
            )
        permitido, mensaje = representacion.puede_crear_publicacion(self.corredor)
        self.assertFalse(permitido)
        self.assertTrue(mensaje)


class DatosPropietarioTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.corredor = User.objects.create_user(
            username="dat_cor", email="dat_cor@x.cl", password="x", rol="corredor"
        )
        cls.gerente = User.objects.create_user(
            username="dat_ger", email="dat_ger@x.cl", password="x", rol="gerente"
        )

    def _post(self, **extra):
        base = {
            "propietario_nombre": "Ana Pérez",
            "propietario_dni": "12.345.678-9",
            "propietario_email": "ana@x.cl",
            "propietario_celular": "+56912345678",
            "tipo_mandato": "escrito",
            "declara_mandato": "1",
        }
        base.update(extra)
        return base

    def test_datos_completos_pasan(self):
        datos, errores = representacion.procesar_datos_propietario(
            self._post(), {"mandato_archivo": "x"}, self.corredor
        )
        self.assertEqual(errores, [])
        self.assertEqual(datos["propietario_nombre"], "Ana Pérez")

    def test_sin_declaracion_jurada_no_pasa(self):
        post = self._post()
        post.pop("declara_mandato")
        datos, errores = representacion.procesar_datos_propietario(
            post, {"mandato_archivo": "x"}, self.corredor
        )
        self.assertEqual(datos["propietario_nombre"], "Ana Pérez")
        self.assertTrue(any("declarar" in e.lower() for e in errores))

    def test_sin_mandato_adjunto_no_pasa(self):
        _, errores = representacion.procesar_datos_propietario(
            self._post(), {}, self.corredor
        )
        self.assertTrue(any("mandato" in e.lower() for e in errores))

    def test_correo_invalido_no_pasa(self):
        _, errores = representacion.procesar_datos_propietario(
            self._post(propietario_email="no-es-correo"),
            {"mandato_archivo": "x"}, self.corredor,
        )
        self.assertTrue(any("correo" in e.lower() for e in errores))

    def test_nombre_demasiado_largo_no_pasa(self):
        _, errores = representacion.procesar_datos_propietario(
            self._post(propietario_nombre="a" * 300),
            {"mandato_archivo": "x"}, self.corredor,
        )
        self.assertTrue(any("255" in e for e in errores))

    def test_mandato_verbal_lo_rechaza_al_corredor(self):
        _, errores = representacion.procesar_datos_propietario(
            self._post(tipo_mandato="verbal"),
            {"mandato_archivo": "x"}, self.corredor,
        )
        self.assertTrue(any("verbal" in e.lower() for e in errores))

    def test_mandato_verbal_lo_acepta_a_la_gerencia_sin_archivo(self):
        datos, errores = representacion.procesar_datos_propietario(
            self._post(tipo_mandato="verbal"), {}, self.gerente
        )
        self.assertEqual(errores, [])
        self.assertEqual(datos["tipo_mandato"], "verbal")

    def test_tipo_de_mandato_obligatorio(self):
        _, errores = representacion.procesar_datos_propietario(
            self._post(tipo_mandato=""), {"mandato_archivo": "x"}, self.corredor
        )
        self.assertTrue(any("mandato" in e.lower() for e in errores))


# ======================================================================
# acciones_de: la máquina de estados de la interfaz
# ======================================================================

class AccionesDeTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.gerente = User.objects.create_user(
            username="acc_ger", email="acc_ger@x.cl", password="x", rol="gerente"
        )
        cls.corredor = User.objects.create_user(
            username="acc_cor", email="acc_cor@x.cl", password="x", rol="corredor"
        )
        cls.propietario = User.objects.create_user(
            username="acc_pro", email="acc_pro@x.cl", password="x", rol="base"
        )
        cls.ajeno = User.objects.create_user(
            username="acc_ajeno", email="acc_ajeno@x.cl", password="x", rol="base"
        )
        cls.propiedad = _crear_propiedad(cls.propietario)
        cls.solicitud = SolicitudPublicacion.objects.create(
            usuario=cls.propietario,
            propiedad=cls.propiedad,
            corredor_asignado=cls.corredor,
            estado="pago_revision",
            meses=1,
        )

    def _acciones(self, user, estado):
        """Acciones de ``user`` con la solicitud en ``estado``."""
        self.solicitud.estado = estado
        return self.solicitud.acciones_de(user)

    def test_el_pago_lo_aprueba_la_gerencia(self):
        self.assertIn("aprobar_pago", self._acciones(self.gerente, "pago_revision"))
        self.assertNotIn(
            "aprobar_pago", self._acciones(self.corredor, "pago_revision")
        )

    def test_asignar_corredor_es_de_la_gerencia(self):
        self.assertIn(
            "asignar_corredor", self._acciones(self.gerente, "pago_aprobado")
        )
        self.assertNotIn(
            "asignar_corredor", self._acciones(self.corredor, "pago_aprobado")
        )

    def test_la_og_la_sube_el_responsable_y_la_aprueba_la_gerencia(self):
        acciones = self._acciones(self.corredor, "en_revision_corredor")
        self.assertIn("subir_og", acciones)
        self.assertNotIn("aprobar_og", acciones)

        self.assertIn("aprobar_og", self._acciones(self.gerente, "og_pendiente"))
        self.assertNotIn(
            "aprobar_og", self._acciones(self.propietario, "og_pendiente")
        )

    def test_usuario_con_dos_roles_recibe_la_union(self):
        # El gerente asignado como responsable: antes se quedaba con los botones
        # de un solo rol y el flujo se atascaba.
        self.solicitud.corredor_asignado = self.gerente
        self.assertIn(
            "subir_og", self._acciones(self.gerente, "en_revision_corredor")
        )
        self.assertIn("aprobar_og", self._acciones(self.gerente, "og_pendiente"))

    def test_el_solicitante_completa_datos_tras_aprobar_la_og(self):
        self.assertIn(
            "completar_datos", self._acciones(self.propietario, "og_aceptada")
        )
        self.assertNotIn(
            "completar_datos", self._acciones(self.propietario, "og_pendiente")
        )

    def test_validar_y_publicar_es_del_responsable(self):
        self.assertIn(
            "validar_publicar", self._acciones(self.corredor, "en_validacion")
        )
        self.assertIn("editar_datos", self._acciones(self.propietario, "en_validacion"))

    def test_un_ajeno_no_tiene_acciones(self):
        for estado in ("pago_revision", "og_pendiente", "en_validacion", "publicada"):
            self.assertEqual(self._acciones(self.ajeno, estado), set(), estado)

    def test_sin_autenticar_no_hay_acciones(self):
        anonimo = SimpleNamespace(is_authenticated=False, rol="")
        self.assertEqual(self.solicitud.acciones_de(anonimo), set())
        self.assertEqual(self.solicitud.acciones_de(None), set())

    def test_enlace_a_la_propiedad_publicada(self):
        self.assertIn(
            "ver_publicada", self._acciones(self.propietario, "publicada")
        )
        self.assertIn("ver_publicada", self._acciones(self.corredor, "publicada"))
        self.assertNotIn("ver_publicada", self._acciones(self.ajeno, "publicada"))
# ======================================================================
# aviso de representación: la única página pública, sin login
# ======================================================================

class AvisoRepresentacionTests(TestCase):
    """El propietario, sin cuenta, entra por un enlace con token.

    Es la superficie de mayor riesgo del flujo: pública, sin login y capaz de
    cambiar el estado de una publicación. Estas pruebas fijan sus garantías.
    """

    TOKEN = "token-de-prueba-1234567890abcdef"

    @classmethod
    def setUpTestData(cls):
        cls.corredor = User.objects.create_user(
            username="avi_cor", email="avi_cor@x.cl", password="x", rol="corredor"
        )
        cls.gerente = User.objects.create_user(
            username="avi_ger", email="avi_ger@x.cl", password="x", rol="gerente"
        )
        cls.propiedad = _crear_propiedad(
            None,
            representante=cls.corredor,
            en_representacion=True,
            propietario_nombre="Rosa Díaz",
            propietario_email="rosa@x.cl",
        )

    def _solicitud(self, **extra):
        datos = {
            "usuario": self.corredor,
            "propiedad": self.propiedad,
            "corredor_asignado": self.corredor,
            "estado": "publicada",
            "tipo_publicante": SolicitudPublicacion.TipoPublicante.REPRESENTANTE,
            "aviso_token": self.TOKEN,
            "objecion_dias": 3,
            # La gerencia fija esta fecha al aprobar el pago; el aviso la muestra.
            "objecion_hasta": timezone.now() + timezone.timedelta(days=3),
        }
        datos.update(extra)
        return SolicitudPublicacion.objects.create(**datos)

    def _url(self, token=None):
        return reverse(
            "aviso_representacion", kwargs={"token": token or self.TOKEN}
        )

    def test_token_inexistente_da_404(self):
        self._solicitud()
        self.assertEqual(self.client.get(self._url("token-inventado")).status_code, 404)

    def test_abrir_el_aviso_queda_registrado(self):
        solicitud = self._solicitud()
        self.assertIsNone(solicitud.aviso_abierto_at)

        respuesta = self.client.get(self._url())

        self.assertEqual(respuesta.status_code, 200)
        # El propietario debe poder reconocer el aviso como suyo y saber hasta
        # cuándo puede oponerse.
        self.assertContains(respuesta, "Rosa Díaz")
        self.assertContains(respuesta, "Puede oponerse hasta")
        solicitud.refresh_from_db()
        self.assertIsNotNone(solicitud.aviso_abierto_at)

    def test_objetar_marca_la_solicitud_y_retira_la_publicacion(self):
        solicitud = self._solicitud()
        PublicacionProp.objects.create(
            propiedad=self.propiedad, publicante=self.corredor,
            estado="publicada", meses=1,
        )
        self.propiedad.estado = "publicada"
        self.propiedad.save(update_fields=["estado"])

        respuesta = self.client.post(
            self._url(), {"motivo": "No autoricé esta publicación"}, follow=True
        )
        self.assertEqual(respuesta.status_code, 200)

        solicitud.refresh_from_db()
        self.assertTrue(solicitud.objetada)
        self.assertEqual(solicitud.estado, "objetada")
        self.assertEqual(solicitud.objecion_motivo, "No autoricé esta publicación")
        self.assertIsNotNone(solicitud.objecion_at)

        self.propiedad.refresh_from_db()
        self.assertEqual(self.propiedad.estado, "archivada")
        self.assertFalse(
            PublicacionProp.objects.filter(
                propiedad=self.propiedad, estado="publicada"
            ).exists()
        )
        # Gerencia y responsable se enteran.
        self.assertTrue(
            Communication.objects.filter(
                recipient=self.gerente, title__icontains="Objeción"
            ).exists()
        )

    def test_objetar_sin_motivo_no_cambia_nada(self):
        solicitud = self._solicitud()

        respuesta = self.client.post(self._url(), {"motivo": "   "})

        self.assertEqual(respuesta.status_code, 200)
        solicitud.refresh_from_db()
        self.assertFalse(solicitud.objetada)
        self.assertEqual(solicitud.estado, "publicada")

    def test_una_segunda_objecion_no_reescribe_el_motivo(self):
        solicitud = self._solicitud()
        self.client.post(self._url(), {"motivo": "Primer motivo"})
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.objecion_motivo, "Primer motivo")

        self.client.post(self._url(), {"motivo": "Segundo motivo"})
        solicitud.refresh_from_db()
        self.assertEqual(solicitud.objecion_motivo, "Primer motivo")

    def test_el_motivo_del_propietario_no_se_interpreta_como_html(self):
        self._solicitud()

        respuesta = self.client.post(
            self._url(), {"motivo": "<script>alert(1)</script>"}
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertNotContains(respuesta, "<script>alert(1)</script>")
# ======================================================================
# paso 1: el formulario donde se elige quién publica
# ======================================================================

class FormularioSolicitarPublicacionTests(TestCase):
    """La pantalla donde se decide si se publica propio o en representación.

    Se revisó en producción y mostraba tres cosas: el comentario de plantilla
    impreso como texto —Django sólo reconoce ``{# #}`` cuando abre y cierra en
    la misma línea—, un desplegable que no dejaba claro qué se elegía y el
    bloque del propietario oculto sin ninguna pista de que existiera.
    """

    @classmethod
    def setUpTestData(cls):
        cls.usuario = User.objects.create_user(
            username="form_usr", email="form_usr@x.cl", password="x", rol="base"
        )
        # La gerencia siempre puede representar: sirve para llegar al parser.
        cls.gerente = User.objects.create_user(
            username="form_ger", email="form_ger@x.cl", password="x", rol="gerente"
        )

    def _pagina(self):
        self.client.force_login(self.usuario)
        return self.client.get(reverse("solicitar_publicacion"))

    def _pagina_gerencia(self):
        self.client.force_login(self.gerente)
        return self.client.get(reverse("solicitar_publicacion"))

    def test_ningun_comentario_de_plantilla_se_imprime(self):
        respuesta = self._pagina()
        self.assertEqual(respuesta.status_code, 200)
        self.assertNotContains(respuesta, "{#")

    def test_ofrece_publicar_como_propietario_o_como_representante(self):
        respuesta = self._pagina()
        # Dos opciones excluyentes y visibles a la vez: radios, no desplegable.
        self.assertContains(respuesta, 'name="tipo_publicante"')
        self.assertContains(respuesta, 'value="propietario"')
        self.assertContains(respuesta, 'value="representante"')
        self.assertContains(respuesta, 'type="radio"')

    def test_los_datos_de_a_quien_se_representa_estan_en_la_pagina(self):
        respuesta = self._pagina()
        self.assertContains(respuesta, 'id="bloque-propietario"')
        self.assertContains(respuesta, 'name="propietario_nombre"')
        self.assertContains(respuesta, 'name="propietario_email"')
        self.assertContains(respuesta, 'name="tipo_mandato"')
        self.assertContains(respuesta, 'name="declara_mandato"')

    def test_el_tipo_de_mandato_llega_con_el_nombre_que_lee_el_servidor(self):
        """El formulario y ``representacion`` deben usar el mismo nombre.

        Estaban desalineados —el formulario mandaba ``mandato_tipo`` y el
        parser leía ``tipo_mandato``—, así que TODA publicación en
        representación rebotaba con "Selecciona el tipo de mandato del
        propietario" aunque el usuario lo hubiera elegido.
        """
        respuesta = self._pagina_gerencia()

        self.assertContains(respuesta, 'name="tipo_mandato"')
        self.assertNotContains(respuesta, 'name="mandato_tipo"')

    def test_publicar_en_representacion_no_rebota_por_el_tipo_de_mandato(self):
        """Un POST con el nombre del formulario no debe fallar por el mandato.

        Queda sin archivo de mandato, así que el rechazo esperado es el del
        archivo. Cualquier queja sobre el tipo de mandato sería el desajuste.
        """
        self.client.force_login(self.gerente)
        respuesta = self.client.post(reverse("solicitar_publicacion"), {
            "tipo_publicante": "representante",
            "propietario_nombre": "Ana Pérez Soto",
            "propietario_dni": "12.345.678-9",
            "propietario_email": "ana@example.com",
            "propietario_celular": "+56912345678",
            "tipo_mandato": "notarial",
            "declara_mandato": "1",
            "calle": "Calle de Prueba",
            "numero_calle": "123",
            "tipo_prop": "casa",
            "tipo_accion": "venta",
            "comuna": "",
        })

        self.assertEqual(respuesta.status_code, 200)
        self.assertNotContains(
            respuesta, "Selecciona el tipo de mandato del propietario"
        )
        # El nombre del propietario vuelve a la pantalla: no se pierde el POST.
        self.assertContains(respuesta, "Ana Pérez Soto")

    def test_la_declaracion_jurada_lleva_la_clase_del_check_redondo(self):
        """Sin esa clase, el diseño global convierte el check en una barra.

        ``.form-modern input`` le quita la apariencia nativa y estira todo
        input al ancho del contenedor: la casilla se marcaba sin que se notara
        el cambio. La clase ``check-declaracion`` es la que le devuelve la
        forma redonda y el relleno coral al marcarla.
        """
        respuesta = self._pagina_gerencia()

        self.assertContains(respuesta, 'class="check-declaracion"')
        self.assertContains(respuesta, 'id="id_declara_mandato"')
# ======================================================================
# paso 1 con una corredora que representa a un propietario
# ======================================================================
#
# El caso reportado: "la corredora Patricia Méndez no puede publicar en
# representación". La causa no estaba en el formulario sino en el plan:
# ``permite_representacion`` nació en ``False`` (migración 0009), nadie lo había
# habilitado, y la pantalla se limitaba a decir "tu plan no lo permite" como
# texto genérico. Estas pruebas fijan las dos mitades del arreglo: que el motivo
# se lea en pantalla y que, con el plan habilitado, el formulario funcione de
# punta a punta — algo que ninguna prueba cubría.
#
# El almacenamiento se cambia a disco local: en producción los archivos van a
# Cloudinary y una prueba no debe depender de la red.

STORAGES_DE_PRUEBA = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"
    },
}


@override_settings(STORAGES=STORAGES_DE_PRUEBA, MEDIA_ROOT=tempfile.mkdtemp())
class PublicarEnRepresentacionTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.corredora = User.objects.create_user(
            username="patricia", email="patricia@x.cl", password="x", rol="corredor"
        )
        cls.plan = PlanSuscripcion.objects.create(
            nombre="Metropoli", tipo="corredor", precio=Decimal("120000"),
            duracion_meses=12, permite_representacion=False,
            max_publicaciones_mensual=15,
        )

    def _suscribir(self, plan=None, dias=30):
        SuscripcionCorredor.objects.update_or_create(
            corredor=self.corredora,
            defaults={
                "plan": plan or self.plan,
                "fecha_fin": timezone.now() + timezone.timedelta(days=dias),
                "activa": True,
            },
        )

    def _url(self):
        return reverse("solicitar_publicacion")

    def _post_representacion(self):
        return {
            "tipo_publicante": "representante",
            "propietario_nombre": "Rosa Díaz",
            "propietario_dni": "12.345.678-9",
            "propietario_email": "rosa@x.cl",
            "propietario_celular": "+56912345678",
            "tipo_mandato": "escrito",
            "declara_mandato": "1",
            "mandato_archivo": SimpleUploadedFile(
                "mandato.pdf", b"mandato firmado",
                content_type="application/pdf",
            ),
            "calle": "Calle de Prueba",
            "numero_calle": "123",
            "tipo_prop": "casa",
            "tipo_accion": "venta",
            "precio": "100000000",
            "meses": "1",
            "fotos": [
                SimpleUploadedFile("casa.jpg", b"foto", content_type="image/jpeg")
            ],
            "comprobante": SimpleUploadedFile(
                "pago.jpg", b"pago", content_type="image/jpeg"
            ),
        }

    # ---------- antes de habilitar el plan ----------

    def test_sin_el_permiso_la_pantalla_dice_el_motivo_concreto(self):
        """No basta con deshabilitar la opción: hay que decir qué falta.

        El nombre del plan es lo que permite pedir la acción correcta —a la
        gerencia, que es quien lo habilita— sin abrir un ticket a ciegas.
        """
        self._suscribir()
        self.client.force_login(self.corredora)

        respuesta = self.client.get(self._url())

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "Metropoli")
        self.assertContains(respuesta, "no incluye publicar en representación")
        # Y la salida concreta, no un "consulta a soporte" a ciegas.
        self.assertContains(respuesta, "Planes de corredor")
        # La opción queda marcada como bloqueada, no sólo inservible. La
        # búsqueda es la clase del elemento —no el nombre del selector, que
        # también vive en el bloque <style>— para no pasar por casualidad.
        self.assertContains(
            respuesta,
            'class="opcion-publicante opcion-publicante--bloqueada"',
        )

    def test_sin_suscripcion_lo_dice_y_no_culpa_al_plan(self):
        self.client.force_login(self.corredora)

        respuesta = self.client.get(self._url())

        self.assertContains(respuesta, "no tiene una suscripción de corredor")
        self.assertNotContains(respuesta, "Metropoli")

    def test_sin_el_permiso_el_post_tampoco_crea_nada(self):
        """La interfaz es comodidad; la frontera la pone el servidor."""
        self._suscribir()
        self.client.force_login(self.corredora)

        respuesta = self.client.post(self._url(), self._post_representacion())

        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(
            SolicitudPublicacion.objects.filter(usuario=self.corredora).exists()
        )

    # ---------- con el permiso habilitado ----------

    def test_con_el_plan_habilitado_llega_al_formulario(self):
        self.plan.permite_representacion = True
        self.plan.save(update_fields=["permite_representacion"])
        self._suscribir()
        self.client.force_login(self.corredora)

        respuesta = self.client.get(self._url())

        self.assertContains(respuesta, "Representaciones este mes")
        self.assertNotContains(
            respuesta,
            'class="opcion-publicante opcion-publicante--bloqueada"',
        )

    def test_con_el_plan_habilitado_crea_la_solicitud_en_representacion(self):
        self.plan.permite_representacion = True
        self.plan.save(update_fields=["permite_representacion"])
        self._suscribir()
        self.client.force_login(self.corredora)

        respuesta = self.client.post(self._url(), self._post_representacion())

        solicitud = SolicitudPublicacion.objects.get(usuario=self.corredora)
        self.assertRedirects(
            respuesta, reverse("detalle_solicitud", args=[solicitud.id])
        )
        self.assertEqual(
            solicitud.tipo_publicante,
            SolicitudPublicacion.TipoPublicante.REPRESENTANTE,
        )
        self.assertEqual(solicitud.estado, "pago_revision")
        self.assertEqual(solicitud.tipo_mandato, "escrito")
        self.assertTrue(solicitud.mandato_archivo)

        propiedad = solicitud.propiedad
        # El propietario queda fuera de la plataforma: sin cuenta y con sus
        # datos declarados en la propiedad.
        self.assertIsNone(propiedad.dueno_id)
        self.assertEqual(propiedad.representante_id, self.corredora.id)
        self.assertTrue(propiedad.en_representacion)
        self.assertEqual(propiedad.propietario_nombre, "Rosa Díaz")
        self.assertEqual(propiedad.propietario_dni, "12.345.678-9")
        self.assertEqual(propiedad.propietario_email, "rosa@x.cl")

    def test_la_suscripcion_vencida_bloquea_aunque_el_plan_permita(self):
        self.plan.permite_representacion = True
        self.plan.save(update_fields=["permite_representacion"])
        self._suscribir(dias=-1)
        self.client.force_login(self.corredora)

        respuesta = self.client.post(self._url(), self._post_representacion())

        self.assertEqual(respuesta.status_code, 200)
        self.assertFalse(
            SolicitudPublicacion.objects.filter(usuario=self.corredora).exists()
        )
# ======================================================================
# el defecto del plan: representar es la regla, no la excepción
# ======================================================================

class DefectoDeRepresentacionTests(TestCase):
    """Un plan de corredor nuevo nace pudiendo representar.

    Con ``default=False`` cada plan creado después de la migración 0011 volvía
    a bloquear la representación, y la corredora lo descubría al llegar al paso
    1 con la opción deshabilitada. Restringir ahora exige desmarcarlo a
    propósito.
    """

    def test_un_plan_nuevo_permite_representar(self):
        plan = PlanSuscripcion.objects.create(
            nombre="Recién creado", tipo="corredor", precio=Decimal("50000"),
            duracion_meses=1,
        )
        self.assertTrue(plan.permite_representacion)

    def test_desmarcarlo_sigue_siendo_posible(self):
        plan = PlanSuscripcion.objects.create(
            nombre="Restringido", tipo="corredor", precio=Decimal("50000"),
            duracion_meses=1, permite_representacion=False,
        )
        self.assertFalse(plan.permite_representacion)


class MotivosDeBloqueoTests(TestCase):
    """Cada motivo nombra la acción y a quién pedírsela.

    El mensaje anterior —"tu cuenta o tu plan actual no permiten publicar en
    representación de terceros"— obligaba a adivinar cuál de las dos cosas era
    y no decía qué hacer. Estos casos cubren las cinco formas de quedar fuera.
    """

    @classmethod
    def setUpTestData(cls):
        cls.corredor = User.objects.create_user(
            username="mot_cor", email="mot_cor@x.cl", password="x", rol="corredor"
        )

    def _plan(self, **extra):
        datos = {
            "nombre": "Metropoli", "tipo": "corredor",
            "precio": Decimal("120000"), "duracion_meses": 12,
        }
        datos.update(extra)
        return PlanSuscripcion.objects.create(**datos)

    def _suscribir(self, plan, activa=True, dias=30):
        return SuscripcionCorredor.objects.create(
            corredor=self.corredor, plan=plan, activa=activa,
            fecha_fin=timezone.now() + timezone.timedelta(days=dias),
        )

    def test_sin_suscripcion_lo_dice_sin_culpar_al_plan(self):
        mensaje = representacion.motivo_no_representar(self.corredor)
        self.assertIn("no tiene una suscripción", mensaje)
        self.assertNotIn("Metropoli", mensaje)

    def test_suscripcion_desactivada_lo_dice(self):
        self._suscribir(self._plan(), activa=False)
        mensaje = representacion.motivo_no_representar(self.corredor)
        self.assertIn("desactivada", mensaje)

    def test_suscripcion_vencida_da_la_fecha(self):
        self._suscribir(self._plan(), dias=-2)
        mensaje = representacion.motivo_no_representar(self.corredor)
        self.assertIn("venció el", mensaje)
        # La fecha concreta: "venció" a secas no dice si fue ayer o hace un año.
        vencimiento = timezone.localtime(
            timezone.now() - timezone.timedelta(days=2)
        )
        self.assertIn(f"{vencimiento:%d-%m-%Y}", mensaje)

    def test_plan_inactivo_lo_dice(self):
        self._suscribir(self._plan(activo=False))
        mensaje = representacion.motivo_no_representar(self.corredor)
        self.assertIn("no está disponible", mensaje)

    def test_plan_sin_el_permiso_nombra_el_plan_y_la_salida(self):
        self._suscribir(self._plan(permite_representacion=False))
        mensaje = representacion.motivo_no_representar(self.corredor)
        self.assertIn("Metropoli", mensaje)
        self.assertIn("Planes de corredor", mensaje)

    def test_la_gerencia_no_tiene_motivo(self):
        gerente = User.objects.create_user(
            username="mot_ger", email="mot_ger@x.cl", password="x", rol="gerente"
        )
        self.assertEqual(representacion.motivo_no_representar(gerente), "")

    def test_la_tupla_sigue_siendo_lo_que_esperan_los_llamadores(self):
        self._suscribir(self._plan())
        permitido, mensaje = representacion.puede_representar(self.corredor)
        self.assertTrue(permitido)
        self.assertEqual(mensaje, "")


# ======================================================================
# el diagnóstico por consola
# ======================================================================

class RevisarRepresentacionCommandTests(TestCase):
    """El comando con que se revisa producción sin abrir el admin."""

    @classmethod
    def setUpTestData(cls):
        cls.corredor = User.objects.create_user(
            username="cmd_cor", email="cmd_cor@x.cl", password="x", rol="corredor"
        )
        cls.plan = PlanSuscripcion.objects.create(
            nombre="Barrio", tipo="corredor", precio=Decimal("60000"),
            duracion_meses=1, permite_representacion=False,
            max_publicaciones_mensual=5,
        )
        SuscripcionCorredor.objects.create(
            corredor=cls.corredor, plan=cls.plan,
            fecha_fin=timezone.now() + timezone.timedelta(days=30),
        )

    def _correr(self, *args):
        from io import StringIO

        from django.core.management import call_command

        salida = StringIO()
        call_command("revisar_representacion", *args, stdout=salida)
        return salida.getvalue()

    def test_informa_el_motivo_del_bloqueo(self):
        salida = self._correr()
        self.assertIn("Barrio", salida)
        self.assertIn("no incluye publicar en representación", salida)

    def test_filtra_por_usuario(self):
        salida = self._correr("--usuario", "cmd_cor@x.cl")
        self.assertIn("cmd_cor@x.cl", salida)
        self.assertNotIn("(sin coincidencias)", salida)

    def test_corregir_habilita_el_plan(self):
        self._correr("--corregir")
        self.plan.refresh_from_db()
        self.assertTrue(self.plan.permite_representacion)
        # Y con el plan habilitado, la corredora puede.
        permitido, mensaje = representacion.puede_representar(self.corredor)
        self.assertTrue(permitido, mensaje)

    def test_corregir_no_toca_los_planes_inactivos(self):
        self.plan.activo = False
        self.plan.save(update_fields=["activo"])
        self._correr("--corregir")
        self.plan.refresh_from_db()
        self.assertFalse(self.plan.permite_representacion)

    def test_corregir_no_toca_los_planes_de_vendedor(self):
        vendedor = PlanSuscripcion.objects.create(
            nombre="Vendedor", tipo="vendedor", precio=Decimal("30000"),
            duracion_meses=1, permite_representacion=False,
        )
        self._correr("--corregir")
        vendedor.refresh_from_db()
        self.assertFalse(vendedor.permite_representacion)
