"""Permisos y persistencia de la edición de propiedad por rol.

Verifica que el botón «Editar propiedad» aparezca sólo a quien corresponde
(admin, gerente y corredor asignado con permiso activo) y que el POST de
edición persista los datos para esos roles y **no** los toque para el resto.
"""
from django.test import TestCase
from django.urls import reverse

from a00seg.models import Comuna, Region, User
from a03Prop.models import CorredorProp, Propiedad


def _crear_propiedad(*, dueno):
    return Propiedad.objects.create(
        dueno=dueno,
        calle="Algarrobo",
        numero_calle="123",
        tipo_prop="departamento",
        tipo_accion="venta",
        tipo_moneda="PCL",
        precio="100000000.00",
        numero_dormitorios=2,
        numero_banos=1,
        tipo_uso="habitacional",
    )


class EdicionPropiedadRolesTest(TestCase):
    def setUp(self):
        self.region = Region.objects.create(nombre="Valparaiso")
        self.comuna_original = Comuna.objects.create(nombre="Algarrobo", region=self.region)
        self.comuna_nueva = Comuna.objects.create(nombre="Vina del Mar", region=self.region)

        self.owner = User.objects.create_user(username="dueno_temp", password="123", rol="base")
        self.admin = User.objects.create_user(username="admin_temp", password="123", rol="superadmin")
        self.gerente = User.objects.create_user(username="gerente_temp", password="123", rol="gerente")
        self.corredor = User.objects.create_user(username="corredor_temp", password="123", rol="corredor")
        self.otro_corredor = User.objects.create_user(username="otro_corredor_temp", password="123", rol="corredor")

        self.propiedad = _crear_propiedad(dueno=self.owner)
        self.propiedad.comuna = self.comuna_original
        self.propiedad.region = self.region
        self.propiedad.save()

        self.corredor_prop = CorredorProp.objects.create(
            propiedad=self.propiedad,
            corredor=self.corredor,
            estado="activa",
            corredor_puede_editar=True,
            dueno_puede_editar=True,
        )

    # ------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------
    def _detalle_url(self):
        return reverse(
            "detalle_propiedad_slug",
            kwargs={"prop_id": self.propiedad.id, "prop_slug": self.propiedad.slug},
        )

    def _editar_url(self):
        return reverse("editar_propiedad", kwargs={"prop_id": self.propiedad.id})

    def _post_edicion(self):
        return self.client.post(
            self._editar_url(),
            {
                "comuna": self.comuna_nueva.id,
                "tipo_uso": "comercial",
                "numero_dormitorios": "5",
                "numero_banos": "4",
                "m_construidos": "123.45",
                "m_terreno": "200",
                "num_estacionamientos": "2",
                "tiene_bodega": "1",
                "descripcion_propiedad": "Descripcion NUEVA de prueba",
                "descripcion_entorno": "Entorno NUEVO de prueba",
                "tipo_moneda": "UF",
                "precio": "9999.00",
            },
        )

    def _assert_datos_actualizados(self):
        self.propiedad.refresh_from_db()
        self.assertEqual(self.propiedad.comuna_id, self.comuna_nueva.id)
        self.assertEqual(self.propiedad.tipo_uso, "comercial")
        self.assertEqual(self.propiedad.numero_dormitorios, 5)
        self.assertEqual(self.propiedad.numero_banos, 4)
        self.assertEqual(str(self.propiedad.m_construidos), "123.45")
        self.assertEqual(str(self.propiedad.m_terreno), "200.00")
        self.assertEqual(self.propiedad.num_estacionamientos, 2)
        self.assertTrue(self.propiedad.tiene_bodega)
        self.assertEqual(self.propiedad.descripcion_propiedad, "Descripcion NUEVA de prueba")
        self.assertEqual(self.propiedad.descripcion_entorno, "Entorno NUEVO de prueba")
        self.assertEqual(self.propiedad.tipo_moneda, "UF")
        self.assertEqual(str(self.propiedad.precio), "9999.00")

    def _reset_datos(self):
        self.propiedad.refresh_from_db()
        self.propiedad.comuna = self.comuna_original
        self.propiedad.tipo_uso = "habitacional"
        self.propiedad.numero_dormitorios = 2
        self.propiedad.numero_banos = 1
        self.propiedad.m_construidos = None
        self.propiedad.m_terreno = None
        self.propiedad.num_estacionamientos = 0
        self.propiedad.tiene_bodega = False
        self.propiedad.descripcion_propiedad = ""
        self.propiedad.descripcion_entorno = ""
        self.propiedad.tipo_moneda = "PCL"
        self.propiedad.precio = "100000000.00"
        self.propiedad.save()

    # ------------------------------------------------------------
    # Botón visible en el detalle (cada rol)
    # ------------------------------------------------------------
    def test_boton_editar_visible_admin(self):
        self.client.force_login(self.admin)
        resp = self.client.get(self._detalle_url())
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Editar propiedad")

    def test_boton_editar_visible_gerente(self):
        self.client.force_login(self.gerente)
        resp = self.client.get(self._detalle_url())
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Editar propiedad")

    def test_boton_editar_visible_corredor_asignado(self):
        self.client.force_login(self.corredor)
        resp = self.client.get(self._detalle_url())
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Editar propiedad")

    def test_boton_editar_oculto_corredor_no_asignado(self):
        self.client.force_login(self.otro_corredor)
        resp = self.client.get(self._detalle_url())
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, "Editar propiedad")

    def test_boton_editar_oculto_corredor_sin_permiso_switch(self):
        self.corredor_prop.corredor_puede_editar = False
        self.corredor_prop.save(update_fields=["corredor_puede_editar"])
        self.client.force_login(self.corredor)
        resp = self.client.get(self._detalle_url())
        self.assertEqual(resp.status_code, 200)
        self.assertNotContains(resp, "Editar propiedad")

    # ------------------------------------------------------------
    # Persistencia de los datos modificados (cada rol)
    # ------------------------------------------------------------
    def test_admin_edita_y_persiste(self):
        self.client.force_login(self.admin)
        resp = self._post_edicion()
        self.assertEqual(resp.status_code, 302)
        self._assert_datos_actualizados()

    def test_gerente_edita_y_persiste(self):
        self.client.force_login(self.gerente)
        resp = self._post_edicion()
        self.assertEqual(resp.status_code, 302)
        self._assert_datos_actualizados()

    def test_corredor_asignado_edita_y_persiste(self):
        self.client.force_login(self.corredor)
        resp = self._post_edicion()
        self.assertEqual(resp.status_code, 302)
        self._assert_datos_actualizados()

    def test_corredor_no_asignado_no_puede_editar(self):
        self.client.force_login(self.otro_corredor)
        resp = self._post_edicion()
        self.assertEqual(resp.status_code, 302)
        self._reset_datos()  # no debe haber cambiado nada relevante
        self.propiedad.refresh_from_db()
        self.assertEqual(self.propiedad.numero_dormitorios, 2)
        self.assertEqual(self.propiedad.tipo_moneda, "PCL")

    def test_corredor_sin_permiso_no_puede_editar(self):
        self.corredor_prop.corredor_puede_editar = False
        self.corredor_prop.save(update_fields=["corredor_puede_editar"])
        self.client.force_login(self.corredor)
        resp = self._post_edicion()
        self.assertEqual(resp.status_code, 302)
        self.propiedad.refresh_from_db()
        self.assertEqual(self.propiedad.numero_dormitorios, 2)
        self.assertEqual(self.propiedad.tipo_moneda, "PCL")
