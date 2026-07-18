# -*- coding: utf-8 -*-
import os, sys, django
os.chdir("c:/Users/sergi/OneDrive/Escritorio/ProyectosDjango/SercaProp")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "SercaProp.settings")
sys.path.insert(0, ".")
django.setup()

from a00seg.models import User, SuscripcionCorredor

print("=" * 120)
print(f"{'Usuario':<20} {'Email':<38} {'Rol':<14} {'Nombres':<20} {'Apellidos':<20} {'DNI':<15} {'Teléfono':<18} {'Validado por':<20} {'Activo':<8} {'Superuser':<10}")
print("=" * 120)

for u in User.objects.all().order_by("-is_superuser", "rol", "username"):
    valido = u.valido_por.get_full_name() if u.valido_por else "-"
    print(f"{u.username:<20} {u.email:<38} {u.get_rol_display():<14} {u.first_name:<20} {u.last_name:<20} {u.dni or '-':<15} {u.cel_phone or '-':<18} {valido:<20} {'✅' if u.is_active else '❌':<8} {'👑' if u.is_superuser else '-':<10}")

print("=" * 120)
print(f"\nTotal: {User.objects.count()} usuarios")

print("\n\n--- SUSCRIPCIONES ACTIVAS ---")
print("=" * 80)
for s in SuscripcionCorredor.objects.filter(activa=True).select_related("corredor", "plan"):
    print(f"{s.corredor.username:<20} | Plan: {s.plan.nombre:<12} | Inicio: {s.fecha_inicio.strftime('%d/%m/%Y'):<12} | Término: {s.fecha_fin.strftime('%d/%m/%Y'):<12} | Props: {s.plan.max_propiedades_simultaneas} máx")
