# -*- coding: utf-8 -*-
import os, sys, django
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "SercaProp.settings")
django.setup()

from django.contrib.auth import get_user_model
User = get_user_model()

for username in ["admin", "Gerente", "Fresia Corredora", "Luis Base"]:
    try:
        u = User.objects.get(username=username)
        print(f"\n=== {username} ===")
        print(f"  Email:          {u.email}")
        print(f"  Rol:            {u.rol}")
        print(f"  is_active:      {u.is_active}")
        print(f"  is_superuser:   {u.is_superuser}")
        print(f"  is_staff:       {u.is_staff}")
        print(f"  valido_por:     {u.valido_por}")
        print(f"  Password 123:   {u.check_password('123')}")
    except User.DoesNotExist:
        print(f"\n=== {username} === NO EXISTE")
