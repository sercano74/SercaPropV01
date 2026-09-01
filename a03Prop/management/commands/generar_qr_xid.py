import os

from django.conf import settings
from django.core.management.base import BaseCommand

import qrcode


class Command(BaseCommand):
    help = (
        "Genera el código QR de la vista /xid/ para el letrero de "
        "comercialización (apunta a propiedades.serca.online/xid/)."
    )

    def handle(self, *args, **options):
        sitio = getattr(settings, "SITE_DOMAIN", "propiedades.serca.online")
        url = f"https://{sitio}/xid/"

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_H,
            box_size=12,
            border=4,
        )
        qr.add_data(url)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")

        filename = "qr-xid.png"
        out_dir = os.path.join(settings.BASE_DIR, "static", "images")
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, filename)
        img.save(out_path)

        self.stdout.write(self.style.SUCCESS(f"QR generado: {out_path}"))
        self.stdout.write(self.style.SUCCESS(f"URL codificada: {url}"))
