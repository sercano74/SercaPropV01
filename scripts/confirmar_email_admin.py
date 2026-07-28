"""
Script para marcar el email del superusuario como confirmado directamente.
Ejecutar en Railway Console: python scripts/confirmar_email_admin.py
"""
import os
import sys
import django

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'SercaProp.settings')
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

try:
    admin = User.objects.get(username='admin')
    if not admin.email_confirmado:
        admin.email_confirmado = True
        admin.save(update_fields=['email_confirmado'])
        print(f"✅ Email de '{admin.username}' confirmado exitosamente.")
    else:
        print(f"ℹ️ El email de '{admin.username}' ya estaba confirmado.")
except User.DoesNotExist:
    print("❌ El usuario 'admin' no existe. Ejecuta primero: python scripts/crear_superuser.py")
