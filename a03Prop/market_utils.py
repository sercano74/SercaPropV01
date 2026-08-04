"""
Utilities for generating marketing images:
- Instagram Story (1080×1920 portrait) for social media sharing
- Facebook Marketplace afiche (1080×1350 portrait) for FB postings

Both images show key property data WITHOUT revealing:
  - Street address / street number
  - Owner's personal data (name, phone, email)
Includes SERCAPROP branding, QR code, and first property photo as background.
"""

import io
import os

from PIL import Image, ImageDraw, ImageFont

import qrcode

# ─── Color palette ───
COLOR_CORAL = "#FF5A5F"
COLOR_DARK = "#484848"
COLOR_MEDIUM = "#767676"
COLOR_WHITE = "#FFFFFF"

# ─── Dimensions ───
STORY_W, STORY_H = 1080, 1920
POSTER_W, POSTER_H = 1080, 1350

# ─── Font paths ───
_FONT_DIR = r"C:\Windows\Fonts"
FONT_BOLD = os.path.join(_FONT_DIR, "segoeuib.ttf")
FONT_REGULAR = os.path.join(_FONT_DIR, "segoeui.ttf")
FONT_ITALIC = os.path.join(_FONT_DIR, "segoeuii.ttf")


def _get_font(path: str, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(path, size)
    except (OSError, IOError):
        try:
            return ImageFont.truetype(FONT_REGULAR, size)
        except (OSError, IOError):
            return ImageFont.load_default()


def _draw_rounded_rect(draw: ImageDraw, xy, radius: int, fill, outline=None, outline_width=0):
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=outline_width)


def _build_qr(url: str, size: int) -> Image.Image:
    qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_H, box_size=6, border=0)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    return img.resize((size, size), Image.LANCZOS)


def _load_first_photo(prop, target_size) -> Image.Image | None:
    """
    Carga la primera foto de la propiedad recortada al target_size.

    Las imágenes están en Cloudinary (MediaCloudinaryStorage), por lo que
    `.path` no existe en producción. Se descarga la imagen desde `.url`
    vía HTTP y fallback a disco local si `.path` existe.
    """
    try:
        first_photo = prop.fotos.first()
        if not first_photo or not first_photo.imagen:
            return None

        photo = None
        # 1) Intentar descargar desde la URL (Cloudinary en producción)
        try:
            url = first_photo.imagen.url
            import requests
            resp = requests.get(url, timeout=15)
            if resp.status_code == 200:
                photo = Image.open(io.BytesIO(resp.content)).convert("RGB")
        except Exception:
            photo = None

        # 2) Fallback: archivo local
        if photo is None:
            path = first_photo.imagen.path
            if os.path.exists(path):
                photo = Image.open(path).convert("RGB")

        if photo is None:
            return None

        tw, th = target_size
        pw, ph = photo.size
        ratio = max(tw / pw, th / ph)
        new_w = int(pw * ratio)
        new_h = int(ph * ratio)
        photo = photo.resize((new_w, new_h), Image.LANCZOS)
        left = (new_w - tw) // 2
        top = (new_h - th) // 2
        photo = photo.crop((left, top, left + tw, top + th))
        return photo
    except Exception:
        return None


def _property_summary(prop) -> dict:
    def fmt_price(val):
        if val is None:
            return ""
        try:
            n = float(val)
            return f"${n:,.0f}"
        except (ValueError, TypeError):
            return str(val)
    return {
        "tipo_prop": prop.get_tipo_prop_display() if prop.tipo_prop else "Propiedad",
        "tipo_accion": prop.get_tipo_accion_display() if prop.tipo_accion else "",
        "precio": fmt_price(prop.precio),
        "moneda": prop.get_tipo_moneda_display(),
        "comuna": str(prop.comuna) if prop.comuna else "",
        "dormitorios": prop.numero_dormitorios,
        "banos": prop.numero_banos,
        "m_construidos": float(prop.m_construidos) if prop.m_construidos else None,
        "m_terreno": float(prop.m_terreno) if prop.m_terreno else None,
        "estacionamientos": prop.num_estacionamientos,
        "tiene_bodega": prop.tiene_bodega,
        "descripcion": (prop.descripcion_propiedad or "")[:200],
    }


def _build_features(data: dict) -> list:
    """Return list of (label, value) tuples for display."""
    features = []
    if data["dormitorios"]:
        features.append(("Dorm.", str(data["dormitorios"])))
    if data["banos"]:
        features.append(("Baños", str(data["banos"])))
    if data["m_construidos"]:
        features.append(("M² Const.", f"{data['m_construidos']:.0f}"))
    if data["m_terreno"]:
        features.append(("M² Terr.", f"{data['m_terreno']:.0f}"))
    if data["estacionamientos"]:
        features.append(("Est.", str(data["estacionamientos"])))
    if data["tiene_bodega"]:
        features.append(("Bodega", "Sí"))
    return features


# ════════════════════════════════════════════════════════════════════
# INSTAGRAM STORY (1080×1920)
# ════════════════════════════════════════════════════════════════════

def generate_instagram_story(prop, url: str) -> bytes:
    bg_photo = _load_first_photo(prop, (STORY_W, STORY_H))

    if bg_photo:
        img = bg_photo
    else:
        img = Image.new("RGB", (STORY_W, STORY_H), COLOR_WHITE)

    overlay = Image.new("RGBA", (STORY_W, STORY_H), (0, 0, 0, 140))
    img = img.convert("RGBA")
    img = Image.alpha_composite(img, overlay)
    img = img.convert("RGB")
    draw = ImageDraw.Draw(img)

    data = _property_summary(prop)
    M = 60

    # ── Top bar ──
    _draw_rounded_rect(draw, (0, 0, STORY_W, 160), radius=0, fill=COLOR_CORAL)
    bf = _get_font(FONT_BOLD, 48)
    t = "SERCA PROPIEDADES"
    bb = bf.getbbox(t)
    draw.text(((STORY_W - bb[2]) // 2, 40), t, fill=COLOR_WHITE, font=bf)
    sf = _get_font(FONT_REGULAR, 22)
    t = "ENCUENTRA TU HOGAR CON NOSOTROS"
    bb = sf.getbbox(t)
    draw.text(((STORY_W - bb[2]) // 2, 100), t, fill=COLOR_WHITE, font=sf)

    # ── Badge ──
    y = 190
    if data["tipo_accion"]:
        bdf = _get_font(FONT_BOLD, 26)
        bt = f"• {data['tipo_accion'].upper()} •"
        bw = bdf.getbbox(bt)[2] + 40
        _draw_rounded_rect(draw, ((STORY_W - bw)//2, y, (STORY_W + bw)//2, y+50), radius=25, fill=COLOR_CORAL)
        draw.text(((STORY_W - bdf.getbbox(bt)[2])//2, y+10), bt, fill=COLOR_WHITE, font=bdf)

    # ── Price ──
    y = 280
    pf = _get_font(FONT_BOLD, 72)
    pt = f"{data['moneda']} {data['precio']}"
    while pf.getbbox(pt)[2] > STORY_W - 2*M and pf.size > 30:
        pf = _get_font(FONT_BOLD, pf.size - 4)
    bb = pf.getbbox(pt)
    draw.text(((STORY_W - bb[2])//2, y), pt, fill=COLOR_WHITE, font=pf)
    y += bb[3] + 24

    # ── Location ──
    if data["comuna"]:
        lf = _get_font(FONT_REGULAR, 32)
        lt = data["comuna"]
        bb = lf.getbbox(lt)
        draw.text(((STORY_W - bb[2])//2, y), lt, fill=COLOR_WHITE, font=lf)
        y += 46

    # ── Property type ──
    tpf = _get_font(FONT_REGULAR, 30)
    tpt = data["tipo_prop"]
    bb = tpf.getbbox(tpt)
    draw.text(((STORY_W - bb[2])//2, y), tpt, fill=COLOR_WHITE, font=tpf)
    y += 50

    # ── Divider ──
    y += 6
    draw.line([((STORY_W-100)//2, y), ((STORY_W+100)//2, y)], fill=COLOR_WHITE, width=2)
    y += 20

    # ── Feature cards (text only) ──
    features = _build_features(data)
    card_y_start = y
    cards_per_row = 4
    card_w = (STORY_W - 2*M - 3*16) // cards_per_row
    card_h = 80

    for idx, (label, val) in enumerate(features[:6]):
        row = idx // cards_per_row
        col = idx % cards_per_row
        cx = M + col * (card_w + 16)
        cy = card_y_start + row * (card_h + 12)
        _draw_rounded_rect(draw, (cx, cy, cx+card_w, cy+card_h), radius=14, fill=(0, 0, 0, 160))
        # value (big)
        vf = _get_font(FONT_BOLD, 30)
        bb = vf.getbbox(val)
        draw.text((cx + (card_w - bb[2])//2, cy + 10), val, fill=COLOR_WHITE, font=vf)
        # label (small)
        lf = _get_font(FONT_REGULAR, 18)
        bb = lf.getbbox(label)
        draw.text((cx + (card_w - bb[2])//2, cy + 50), label, fill=COLOR_WHITE, font=lf)

    # ── Description ──
    if data["descripcion"]:
        df = _get_font(FONT_ITALIC, 22)
        desc_y = card_y_start + max(len(features), 1)*(card_h + 12) + 20
        # simple word wrap
        words = data["descripcion"].split()
        lines = []
        cur = ""
        for w in words:
            test = f"{cur} {w}".strip()
            if df.getbbox(test)[2] <= STORY_W - 2*M:
                cur = test
            else:
                if cur:
                    lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
        for line in lines[:4]:
            bb = df.getbbox(line)
            draw.text(((STORY_W - bb[2])//2, desc_y), line, fill=COLOR_WHITE, font=df)
            desc_y += bb[3] + 6

    # ── QR ──
    qs = 160
    qr = _build_qr(url, qs)
    img.paste(qr, (STORY_W - qs - M, STORY_H - qs - 180))
    qlf = _get_font(FONT_REGULAR, 20)
    qt = "Escanea para más info"
    bb = qlf.getbbox(qt)
    draw.text((STORY_W - qs - M - bb[2] - 20, STORY_H - qs - 180 + qs//2 - 10), qt, fill=COLOR_WHITE, font=qlf)

    # ── Bottom bar ──
    _draw_rounded_rect(draw, (0, STORY_H-60, STORY_W, STORY_H), radius=0, fill=COLOR_CORAL)
    cf = _get_font(FONT_REGULAR, 18)
    ct = "www.sercaprop.cl | contacto@sercaprop.cl"
    bb = cf.getbbox(ct)
    draw.text(((STORY_W - bb[2])//2, STORY_H - 42), ct, fill=COLOR_WHITE, font=cf)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.getvalue()


# ════════════════════════════════════════════════════════════════════
# FACEBOOK MARKETPLACE / AFICHE (1080×1350)
# ════════════════════════════════════════════════════════════════════

def generate_facebook_poster(prop, url: str) -> bytes:
    M = 50
    img = Image.new("RGB", (POSTER_W, POSTER_H), COLOR_WHITE)
    photo_h = int(POSTER_H * 0.6)
    bg_photo = _load_first_photo(prop, (POSTER_W, photo_h))

    if bg_photo:
        overlay = Image.new("RGBA", (POSTER_W, photo_h), (0, 0, 0, 120))
        bg_photo = bg_photo.convert("RGBA")
        bg_photo = Image.alpha_composite(bg_photo, overlay)
        img.paste(bg_photo.convert("RGB"), (0, 0))
        d = ImageDraw.Draw(img)
        d.rectangle([(0, photo_h), (POSTER_W, POSTER_H)], fill="#FBF8F4")
    else:
        d = ImageDraw.Draw(img)
        d.rectangle([(0, 0), (POSTER_W, POSTER_H)], fill="#FBF8F4")

    draw = ImageDraw.Draw(img)
    data = _property_summary(prop)

    # ── Top bar ──
    _draw_rounded_rect(draw, (0, 0, POSTER_W, 120), radius=0, fill=COLOR_CORAL)
    bf = _get_font(FONT_BOLD, 40)
    t = "SERCA PROPIEDADES"
    bb = bf.getbbox(t)
    draw.text(((POSTER_W - bb[2])//2, 30), t, fill=COLOR_WHITE, font=bf)
    sf = _get_font(FONT_REGULAR, 18)
    t = "ENCUENTRA TU HOGAR CON NOSOTROS"
    bb = sf.getbbox(t)
    draw.text(((POSTER_W - bb[2])//2, 80), t, fill=COLOR_WHITE, font=sf)

    # ── Badge ──
    y = 155
    bdf = _get_font(FONT_BOLD, 28)
    bt = data["tipo_accion"].upper() if data["tipo_accion"] else "PROPIEDAD"
    bw = bdf.getbbox(bt)[2] + 40
    _draw_rounded_rect(draw, (M, y-5, M+bw, y+45), radius=22, fill=COLOR_CORAL)
    draw.text((M+20, y+5), bt, fill=COLOR_WHITE, font=bdf)

    tpf = _get_font(FONT_BOLD, 24)
    tpt = data["tipo_prop"]
    draw.text((M+bw+20, y+5), tpt, fill=COLOR_WHITE, font=tpf)
    y += 70

    # ── Price ──
    pf = _get_font(FONT_BOLD, 64)
    pt = f"{data['moneda']} {data['precio']}"
    while pf.getbbox(pt)[2] > POSTER_W - 2*M and pf.size > 28:
        pf = _get_font(FONT_BOLD, pf.size - 4)
    bb = pf.getbbox(pt)
    draw.text(((POSTER_W - bb[2])//2, y), pt, fill=COLOR_WHITE, font=pf)
    y += bb[3] + 16

    # ── Location ──
    if data["comuna"]:
        lf = _get_font(FONT_BOLD, 28)
        lt = data["comuna"]
        bb = lf.getbbox(lt)
        draw.text(((POSTER_W - bb[2])//2, y), lt, fill=COLOR_WHITE, font=lf)
        y += 44

    # ── Divider ──
    y += 8
    draw.line([(M, y), (POSTER_W-M, y)], fill=COLOR_WHITE, width=2)
    y += 18

    # ── Feature cards ──
    features = _build_features(data)
    cpr = 2 if len(features) >= 4 else 3
    cw = (POSTER_W - 2*M - (cpr-1)*16) // cpr
    ch = 90

    for idx, (label, val) in enumerate(features[:6]):
        row = idx // cpr
        col = idx % cpr
        cx = M + col * (cw + 16)
        cy = y + row * (ch + 12)
        _draw_rounded_rect(draw, (cx, cy, cx+cw, cy+ch), radius=12, fill=(255, 255, 255, 220),
                           outline="#E0E0E0", outline_width=2)
        lf = _get_font(FONT_REGULAR, 18)
        bb = lf.getbbox(label)
        draw.text((cx + (cw - bb[2])//2, cy + 14), label, fill=COLOR_MEDIUM, font=lf)
        vf = _get_font(FONT_BOLD, 28)
        bb = vf.getbbox(val)
        draw.text((cx + (cw - bb[2])//2, cy + 50), val, fill=COLOR_DARK, font=vf)

    # ── Description ──
    desc_y = y + ((max(len(features), 2)+1)//2)*(ch+12) + 10
    if data["descripcion"]:
        df = _get_font(FONT_ITALIC, 20)
        words = data["descripcion"].split()
        lines = []
        cur = ""
        for w in words:
            test = f"{cur} {w}".strip()
            if df.getbbox(test)[2] <= POSTER_W - 2*M:
                cur = test
            else:
                if cur:
                    lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
        for line in lines[:5]:
            bb = df.getbbox(line)
            draw.text(((POSTER_W - bb[2])//2, desc_y), line, fill=COLOR_MEDIUM, font=df)
            desc_y += bb[3] + 4

    # ── QR ──
    qs = 140
    qr = _build_qr(url, qs)
    qrx = POSTER_W - qs - M
    qry = POSTER_H - qs - 100
    img.paste(qr, (qrx, qry))

    qlf = _get_font(FONT_REGULAR, 16)
    qt = "Escanea para más info"
    bb = qlf.getbbox(qt)
    draw.text((qrx - bb[2] - 20, qry + qs//2 - 10), qt, fill=COLOR_DARK, font=qlf)

    # ── CTA ──
    cta = "Ver detalle completo"
    cf = _get_font(FONT_BOLD, 22)
    cw2 = cf.getbbox(cta)[2] + 36
    ch2 = 52
    _draw_rounded_rect(draw, (M, qry + qs//2 - ch2//2, M+cw2, qry + qs//2 + ch2//2), radius=26, fill=COLOR_CORAL)
    bb = cf.getbbox(cta)
    draw.text((M + (cw2 - bb[2])//2, qry + qs//2 - bb[3]//2), cta, fill=COLOR_WHITE, font=cf)

    # ── Bottom bar ──
    _draw_rounded_rect(draw, (0, POSTER_H-50, POSTER_W, POSTER_H), radius=0, fill=COLOR_CORAL)
    cf2 = _get_font(FONT_REGULAR, 16)
    ct = "www.sercaprop.cl | contacto@sercaprop.cl"
    bb = cf2.getbbox(ct)
    draw.text(((POSTER_W - bb[2])//2, POSTER_H - 34), ct, fill=COLOR_WHITE, font=cf2)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.getvalue()
