"""
Poster generator for printable flyers (A4).
Produces a PDF with "SERCAPROP" branding and a QR code linking to the property detail page.
Design: modern, elegant, Airbnb-inspired color palette.
"""

import io
import os
import qrcode
from django.conf import settings
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm, cm
from reportlab.lib.colors import HexColor, white, black
from reportlab.pdfgen import canvas


# Airbnb-inspired color palette
COLOR_CORAL = HexColor("#FF5A5F")      # Airbnb red/coral
COLOR_TEAL = HexColor("#00A699")       # Airbnb teal
COLOR_DARK = HexColor("#484848")       # Dark gray text
COLOR_MEDIUM = HexColor("#767676")     # Medium gray
COLOR_LIGHT_BG = HexColor("#F7F7F7")   # Light background
COLOR_WHITE = white
COLOR_BLACK = black


def _draw_qr_code(c: canvas.Canvas, url: str, x: float, y: float, size_mm: float) -> None:
    """Generate and draw a QR code at position (x, y) with given size in mm."""
    qr = qrcode.QRCode(
        version=None,  # auto-detect
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=4,
        border=0,
    )
    qr.add_data(url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    # Save QR to a temp file (reportlab drawImage needs a path or PIL Image)
    temp_path = os.path.join(settings.MEDIA_ROOT, "_temp_qr.png")
    os.makedirs(os.path.dirname(temp_path), exist_ok=True)
    img.save(temp_path, format="PNG")

    c.drawImage(
        temp_path, x, y - size_mm,
        width=size_mm, height=size_mm,
        preserveAspectRatio=True,
        mask="auto",
    )

    # Clean up temp file
    try:
        os.remove(temp_path)
    except OSError:
        pass


def generate_poster(url: str) -> bytes:
    """
    Generate a print-ready A4 poster PDF with SERCAPROP branding and QR code.

    Args:
        url: Absolute URL the QR code should point to (property detail page).

    Returns:
        PDF content as bytes.
    """
    buf = io.BytesIO()
    page_w, page_h = A4  # 210mm x 297mm
    margin = 20 * mm

    c = canvas.Canvas(buf, pagesize=A4)

    # ── Background: white with a thin coral border ──
    c.setStrokeColor(COLOR_CORAL)
    c.setLineWidth(1.5)
    c.rect(margin, margin, page_w - 2 * margin, page_h - 2 * margin)
    c.setFillColor(COLOR_LIGHT_BG)
    c.rect(margin + 1.5, margin + 1.5, page_w - 2 * margin - 3, page_h - 2 * margin - 3, fill=1, stroke=0)

    # ── Top accent bar ──
    bar_height = 6 * mm
    c.setFillColor(COLOR_CORAL)
    c.rect(0, page_h - bar_height, page_w, bar_height, fill=1, stroke=0)

    # ── Bottom accent bar ──
    c.setFillColor(COLOR_TEAL)
    c.rect(0, 0, page_w, bar_height, fill=1, stroke=0)

    # ══════════════════════════════════════════════
    # BRAND: SERCAPROP
    # ══════════════════════════════════════════════
    brand_center_x = page_w / 2
    brand_y = page_h - 40 * mm

    # Subtitle (small, above main name)
    c.setFillColor(COLOR_MEDIUM)
    c.setFont("Helvetica", 22)
    subtitle = "VENDE O ARRIENDA CON NOSOTROS"
    c.drawCentredString(brand_center_x, brand_y, subtitle)

    # Main brand name
    brand_y -= 24 * mm
    c.setFillColor(COLOR_CORAL)
    c.setFont("Helvetica-Bold", 42)
    c.drawCentredString(brand_center_x, brand_y, "SERCA PROPIEDADES")
    
    # Thin decorative line under brand
    line_y = brand_y - 10 * mm
    c.setStrokeColor(COLOR_CORAL)
    c.setLineWidth(0.8)
    line_width = 60 * mm
    c.line(
        brand_center_x - line_width / 2, line_y,
        brand_center_x + line_width / 2, line_y,
    )

    # ── QR Code ──
    qr_size = 90 * mm
    qr_y = line_y - qr_size + 50 * mm
    _draw_qr_code(c, url, brand_center_x - qr_size / 2, qr_y, qr_size)

    # ── Instruction text below QR ──
    instr_y = qr_y + 15 * mm
    c.setFillColor(COLOR_MEDIUM)
    c.setFont("Helvetica", 11)
    instr_text = "Escanea el código QR para ver el detalle de esta propiedad"
    c.drawCentredString(brand_center_x, instr_y, instr_text)

    # ── Tagline / slogan at bottom ──
    tagline_y = 38 * mm
    c.setFillColor(COLOR_TEAL)
    c.setFont("Helvetica-Bold", 14)
    tagline = "ENCUENTRA TU HOGAR CON NOSOTROS"
    c.drawCentredString(brand_center_x, tagline_y, tagline)

    # ── Contact info at very bottom ──
    contact_y = 8 * mm
    c.setFillColor(COLOR_MEDIUM)
    c.setFont("Helvetica", 8)
    contact_text = "www.sercaprop.cl | contacto@sercaprop.cl | +56 9 3691 6684"
    c.drawCentredString(brand_center_x, contact_y, contact_text)

    c.showPage()
    c.save()

    buf.seek(0)
    return buf.getvalue()
