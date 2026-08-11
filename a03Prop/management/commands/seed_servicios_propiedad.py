from django.core.management.base import BaseCommand
from a03Prop.models import ServiciosProp

# (nombre, icono, categoria)
SERVICIOS = [
    # ===== ENTORNO Y UBICACIÓN =====
    ("Cercano a centros de salud", "fa-solid fa-hospital", "entorno"),
    ("Cercano a colegios y universidades", "fa-solid fa-graduation-cap", "entorno"),
    ("Cerca de transporte público / Metro", "fa-solid fa-train-subway", "entorno"),
    ("Cercano a centros comerciales", "fa-solid fa-cart-shopping", "entorno"),
    ("Cercano a parques y áreas verdes", "fa-solid fa-tree", "entorno"),
    ("Excelente conectividad / Accesos", "fa-solid fa-road", "entorno"),
    ("Zona residencial tranquila", "fa-solid fa-house-chimney", "entorno"),

    # ===== EQUIPAMIENTO E INSTALACIONES (CONDOMINIO / EDIFICIO) =====
    ("Seguridad 24/7 y Conserjería", "fa-solid fa-shield-halved", "equipamiento"),
    ("Estacionamiento de visitas", "fa-solid fa-square-parking", "equipamiento"),
    ("Piscina", "fa-solid fa-water-ladder", "equipamiento"),
    ("Gimnasio equipado", "fa-solid fa-dumbbell", "equipamiento"),
    ("Quincho / Zona de asados", "fa-solid fa-fire-burner", "equipamiento"),
    ("Sala de eventos / Lounge", "fa-solid fa-champagne-glasses", "equipamiento"),
    ("Área de juegos infantiles", "fa-solid fa-child-reaching", "equipamiento"),
    ("Coworking / Sala de reuniones", "fa-solid fa-laptop-code", "equipamiento"),
    ("Bicicletero", "fa-solid fa-bicycle", "equipamiento"),
    ("Ascensores", "fa-solid fa-elevator", "equipamiento"),

    # ===== CARACTERÍSTICAS DE LA PROPIEDAD (INTERIOR) =====
    ("Admite mascotas (Pet Friendly)", "fa-solid fa-paw", "interior"),
    ("Aire acondicionado / Climatización", "fa-solid fa-snowflake", "interior"),
    ("Calefacción central", "fa-solid fa-radiator", "interior"),
    ("Terraza / Balcón", "fa-solid fa-sun-plant-wilt", "interior"),
    ("Logia / Loggia independiente", "fa-solid fa-jug-detergent", "interior"),
    ("Bodega / Almacenamiento", "fa-solid fa-box-open", "interior"),
    ("Cocina equipada / Amoblada", "fa-solid fa-kitchen-set", "interior"),
    ("Portón eléctrico / Acceso remoto", "fa-solid fa-car", "interior"),
    ("Conexión a Internet / Fibra óptica", "fa-solid fa-wifi", "interior"),
    ("Paneles solares / Eficiencia energética", "fa-solid fa-bolt", "interior"),
]


class Command(BaseCommand):
    help = "Crea o actualiza los servicios/características de propiedades (categorizados)."

    def handle(self, *args, **options):
        creados = 0
        actualizados = 0
        for nombre, icono, categoria in SERVICIOS:
            obj, created = ServiciosProp.objects.update_or_create(
                nombre=nombre,
                defaults={"icono": icono, "categoria": categoria, "is_active": True},
            )
            if created:
                creados += 1
            else:
                actualizados += 1
        self.stdout.write(self.style.SUCCESS(
            f"✅ Servicios listos: {creados} creados, {actualizados} actualizados "
            f"(total {ServiciosProp.objects.count()})."
        ))
