"""
Script para crear el superusuario admin en Railway.
Ejecutar:  python scripts/crear_superuser.py

O desde Railway Console:
  1. Ve a tu proyecto Railway → web → Console
  2. Escribe:  python scripts/crear_superuser.py
"""
import os
import sys
import django

# Asegurar que /app esté en el path (Railway ejecuta desde /app)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'SercaProp.settings')
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

admin_data = {
    'username': 'admin',
    'email': 'ordered.dev.01@gmail.com',
    'password': '123',
    'rol': 'superadmin',
    'is_staff': True,
    'is_superuser': True,
}

user, created = User.objects.get_or_create(
    username=admin_data['username'],
    defaults={k: v for k, v in admin_data.items() if k != 'password'}
)

if created:
    user.set_password(admin_data['password'])
    user.save()
    print(f"✅ Superusuario '{admin_data['username']}' creado exitosamente")
else:
    user.is_staff = True
    user.is_superuser = True
    user.rol = 'superadmin'
    user.set_password(admin_data['password'])
    user.save()
    print(f"✅ Superusuario '{admin_data['username']}' actualizado")

print(f"\n   Usuario: {admin_data['username']}")
print(f"   Email:   {admin_data['email']}")
print(f"   Password: {admin_data['password']}")
