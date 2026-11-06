"""Diagnóstico de la publicación en representación, corredor por corredor.

Existe por un caso concreto: una corredora con plan vigente veía la opción
"Represento al propietario" deshabilitada y un mensaje que no decía qué
faltaba. La causa estaba en los datos —el plan no tenía
``permite_representacion``—, no en el flujo, y desde la aplicación no había
forma de comprobarlo sin abrir el admin de Django.

Uso en producción (Railway):

    python manage.py revisar_representacion
    python manage.py revisar_representacion --usuario patricia@ejemplo.cl
    python manage.py revisar_representacion --corregir

``--corregir`` habilita la representación en los planes de corredor **activos**
que la tengan deshabilitada. Es el mismo criterio de la migración 0012: un
plan de corredor activo nace habilitado, y la gerencia lo desmarca desde
*Gestión → Planes de corredor* si quiere restringirlo.
"""
from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from a00seg.models import PlanSuscripcion, SuscripcionCorredor

from a03Prop import representacion


class Command(BaseCommand):
    help = "Revisa por qué un corredor puede o no publicar en representación."

    def add_arguments(self, parser):
        parser.add_argument(
            "--usuario",
            dest="usuario",
            default="",
            help="Email o username de un corredor concreto.",
        )
        parser.add_argument(
            "--corregir",
            action="store_true",
            default=False,
            help=(
                "Habilita la representación en los planes de corredor activos "
                "que la tengan deshabilitada."
            ),
        )

    def handle(self, *args, **opciones):
        if opciones["corregir"]:
            self._corregir_planes()

        self.stdout.write(self.style.MIGRATE_HEADING("\nPlanes de corredor"))
        self._listar_planes()

        self.stdout.write(self.style.MIGRATE_HEADING("\nCorredores"))
        self._listar_corredores(opciones["usuario"])

    # ------------------------------------------------------------------
    # Planes
    # ------------------------------------------------------------------

    def _listar_planes(self):
        planes = PlanSuscripcion.objects.filter(tipo="corredor").order_by("nombre")
        if not planes:
            self.stdout.write("  (no hay planes de corredor)")
            return

        for plan in planes:
            activos = SuscripcionCorredor.objects.filter(
                plan=plan, activa=True
            ).count()
            estado = "sí" if plan.permite_representacion else "NO"
            self.stdout.write(
                f"  [{plan.id}] {plan.nombre:<20} "
                f"activo={'sí' if plan.activo else 'no':<3} "
                f"representación={estado:<3} "
                f"cupo={plan.max_publicaciones_mensual:<3} "
                f"suscripciones_activas={activos}"
            )

    def _corregir_planes(self):
        pendientes = PlanSuscripcion.objects.filter(
            tipo="corredor", activo=True, permite_representacion=False
        )
        nombres = list(pendientes.values_list("nombre", flat=True))
        if not nombres:
            self.stdout.write(
                self.style.SUCCESS(
                    "\nTodos los planes de corredor activos ya permiten representar."
                )
            )
            return
        cambiados = pendientes.update(permite_representacion=True)
        self.stdout.write(
            self.style.SUCCESS(
                f"\nHabilitada la representación en {cambiados} plan(es): "
                f"{', '.join(nombres)}."
            )
        )

    # ------------------------------------------------------------------
    # Corredores
    # ------------------------------------------------------------------

    def _listar_corredores(self, filtro):
        corredores = SuscripcionCorredor.objects.select_related(
            "corredor", "plan"
        ).order_by("corredor__first_name", "corredor__username")

        if filtro:
            corredores = corredores.filter(
                Q(corredor__email__iexact=filtro)
                | Q(corredor__username__iexact=filtro)
            )

        if not corredores:
            self.stdout.write("  (sin coincidencias)")
            return

        for suscripcion in corredores:
            self._informar_corredor(suscripcion)

    def _informar_corredor(self, suscripcion):
        corredor = suscripcion.corredor
        plan = suscripcion.plan
        permitido, motivo = representacion.puede_representar(corredor)
        usadas, limite = representacion.cupo_del_mes(corredor)

        vencida = (
            suscripcion.fecha_fin and suscripcion.fecha_fin <= timezone.now()
        )
        marca = self.style.SUCCESS("OK  ") if permitido else self.style.ERROR("NO  ")

        self.stdout.write("")
        self.stdout.write(
            f"  {marca}{corredor.get_full_name() or corredor.username} "
            f"<{corredor.email}> (rol={corredor.rol}, activo={corredor.is_active})"
        )
        self.stdout.write(
            f"       plan={plan.nombre} "
            f"suscripción={'activa' if suscripcion.activa else 'inactiva'} "
            f"vence={suscripcion.fecha_fin:%Y-%m-%d}"
            f"{' (VENCIDA)' if vencida else ''} "
            f"plan_representación={'sí' if plan.permite_representacion else 'NO'}"
        )
        self.stdout.write(
            f"       cupo del mes: {usadas}"
            f"{f' de {limite}' if limite is not None else ' (sin tope)'}"
        )
        if not permitido:
            self.stdout.write(self.style.WARNING(f"       motivo: {motivo}"))
