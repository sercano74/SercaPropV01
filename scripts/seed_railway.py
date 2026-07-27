"""
Script para poblar la base de datos en Railway con usuarios de prueba.
Ejecutar después del deploy: python scripts/seed_railway.py
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'SercaProp.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password

User = get_user_model()

users_data = [
    {
        'username': 'admin',
        'email': 'ordered.dev.01@gmail.com',
        'password': '123',
        'rol': 'superadmin',
        'is_staff': True,
        'is_superuser': True,
    },
    {
        'username': 'Gerente',
        'email': 'sercapropgerente@gmail.com',
        'password': '123',
        'rol': 'gerente',
    },
    {
        'username': 'Danna Smith',
        'email': 'cannobbiosergio9@gmail.com',
        'password': '123',
        'rol': 'corredor',
    },
    {
        'username': 'Luis Pitersen',
        'email': 'sergiocannobbio@libertarios6r.lat',
        'password': '123',
        'rol': 'usuario',
    },
    {
        'username': 'Sergio Pérez',
        'email': 'sergiocannobbio@gmail.com',
        'password': '123',
        'rol': 'usuario',
    },
]

for data in users_data:
    password = data.pop('password')
    user, created = User.objects.get_or_create(
        username=data['username'],
        defaults=data,
    )
    if created:
        user.set_password(password)
        user.save()
        print(f"✓ Usuario '{user.username}' creado")
    else:
        print(f"- Usuario '{user.username}' ya existe")

print("\nSeed completado.")
