import os, sys, django
os.chdir("c:/Users/sergi/OneDrive/Escritorio/ProyectosDjango/SercaProp")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "SercaProp.settings")
sys.path.insert(0, ".")
django.setup()
from a00seg.models import User
u = User.objects.get(username="Gerente")
u.email = "sercapropgerente@gmail.com"
u.save()
print(f"✅ Email del Gerente actualizado a: {u.email}")
