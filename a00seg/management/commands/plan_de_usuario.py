"""Muestra el plan de suscripción de un usuario, buscándolo por nombre o email.

Responde a la pregunta "¿en qué plan está Fulano?" sin abrir el admin ni
escribir Python a mano. Sirve igual en local (SQLite) y en producción
(Postgres de Railway), así que el mismo comando vale en los dos entornos:

    python manage.py plan_de_usuario patricia
    python manage.py plan_de_usuario patricia@ejemplo.cl
    python manage.py plan_de_usuario            # todos, en tabla

Sin argumentos lista a todo el mundo para poder revisar el padrón completo.
"""
from django.core.management.base import BaseCommand
from django.db.models import Q

from a00seg.models import User


class Command(BaseCommand):
    help = "Muestra el plan de suscripción de un usuario (por nombre, usuario o email)."

    def add_arguments(self, parser):
        parser.add_argument(
            "buscar",
            nargs="?",
            help="Parte del nombre, del usuario o del email. Sin esto, lista a todos.",
        )

    def handle(self, *args, **opciones):
        termino = opciones.get("buscar")
        usuarios = User.objects.all().order_by("id")

        if termino:
            usuarios = usuarios.filter(
                Q(username__icontains=termino)
                | Q(email__icontains=termino)
                | Q(first_name__icontains=termino)
                | Q(last_name__icontains=termino)
            )

        encontrados = list(usuarios)
        if not encontrados:
            self.stdout.write(self.style.WARNING(
                f"No hay ningún usuario que coincida con «{termino}»."
            ))
            return

        self.stdout.write(f"{'ID':<5} {'USUARIO':<22} {'NOMBRE':<24} {'ROL':<11} PLAN")
        self.stdout.write("-" * 92)

        for usuario in encontrados:
            self.stdout.write(
                f"{usuario.id:<5} {usuario.username[:21]:<22} "
                f"{(usuario.get_full_name() or '-')[:23]:<24} "
                f"{usuario.rol:<11} {self._describir_plan(usuario)}"
            )

        self.stdout.write("-" * 92)
        self.stdout.write(f"{len(encontrados)} usuario(s).")

    def _describir_plan(self, usuario):
        """Texto del plan, con su estado actual, o el motivo de no tenerlo."""
        suscripcion = getattr(usuario, "suscripcion", None)
        if suscripcion:
            return self._formato(
                "corredor", suscripcion.plan, suscripcion
            )

        suscripcion_vendedor = getattr(usuario, "suscripcion_vendedor", None)
        if suscripcion_vendedor:
            return self._formato(
                "vendedor", suscripcion_vendedor.plan, suscripcion_vendedor
            )

        if usuario.rol == "corredor":
            # Un corredor sin suscripción es un caso real: postuló, la gerencia
            # lo aprobó y la suscripción no llegó a crearse. Hay que verlo.
            return "SIN SUSCRIPCIÓN (es corredor y no tiene plan asignado)"

        return "sin plan"

    def _formato(self, tipo, plan, suscripcion):
        estado = "activa" if suscripcion.activa else "INACTIVA"
        return (
            f"{plan.nombre} ({tipo}) · ${plan.precio:.0f} · {estado} · "
            f"vence {suscripcion.fecha_fin:%d/%m/%Y}"
        )
