# -*- coding: utf-8 -*-
import os, sys, django
os.chdir("c:/Users/sergi/OneDrive/Escritorio/ProyectosDjango/SercaProp")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "SercaProp.settings")
sys.path.insert(0, ".")
django.setup()

from django.utils import timezone
from a00seg.models import SuscripcionCorredor, PlanSuscripcion, User

fresia = User.objects.get(username="Fresia Corredora")
plan = PlanSuscripcion.objects.get(nombre="SuperHouse")

fecha_fin = timezone.now() + timezone.timedelta(days=365)
susc, created = SuscripcionCorredor.objects.update_or_create(
    corredor=fresia,
    defaults={
        "plan": plan,
        "fecha_fin": fecha_fin,
        "activa": True,
    }
)
print(f"✅ Suscripción {'creada' if created else 'actualizada'} para Fresia: Plan {plan.nombre}, vence {fecha_fin.strftime('%d/%m/%Y')}")
